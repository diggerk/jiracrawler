#!/usr/bin/env python -W ignore::DeprecationWarning

import sys

import logging

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError

from jiracrawler.model import Base, Version, Issue, Worklog, Status
from jirareports.common import JiraConnection


logger = logging.getLogger(__name__)


class JiraCrawler(object):

    def __init__(self):
        logger.info("Establishing JIRA connection")
        self.jira_con = JiraConnection()
        #self.jira_con = JiraConnection(provider='SOAPpy')
        (self.auth, self.jira, self.project_name) = (
            self.jira_con.auth, self.jira_con.service, self.jira_con.project_name)

        db_name = '%s_jira' % self.jira_con.project_name.lower()
        logger.info("Using database %s to store data")
        self.engine = create_engine('mysql://root:@localhost/%s' % db_name, echo=False)
        self.engine.connect()

        Base.metadata.create_all(self.engine)

        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        self.project = self.jira.getProjectByKey(self.auth, self.project_name)

        self.issue_types = {}
        for t in self.jira.getSubTaskIssueTypesForProject(self.auth, self.project.id):
            self.issue_types[t.id] = t
        for t in self.jira.getIssueTypesForProject(self.auth, self.project.id):
            self.issue_types[t.id] = t

        logger.info("Received %s issue types", len(self.issue_types))

    def store_issue(self, issue, issue_model, version_model):
        issue_model.key = issue.key
        issue_model.type = self.issue_types[issue.type].name
        issue_model.subtask = self.issue_types[issue.type].subTask
        issue_model.summary = issue.summary
        issue_model.assignee = issue.assignee
        issue_model.created_at = self.jira_con.to_datetime(issue.created)
        issue_model.status = self.statuses[int(issue.status)]
        issue_model.fix_version = version_model

        if issue.duedate:
            issue_model.due_date = self.jira_con.to_datetime(issue.duedate)

        return self.session.merge(issue_model)

    def update_issue(self, version_model, issue):
        issue_model = self.session.query(Issue).get(int(issue.id))
        return self.store_issue(issue, issue_model, version_model)

    def create_issue(self, version_model, issue):
        issue_model = Issue(id=int(issue.id))
        return self.store_issue(issue, issue_model, version_model)

    def update_statuses(self):
        self.statuses = {}
        for status in self.jira.getStatuses(self.auth):
            s = Status(id=int(status.id), name=status.name)
            s = self.session.merge(s)
            self.statuses[s.id] = s

    def update_issues_and_worklogs(self, versions = None):
        active_versions = []

        existing_issues = set(int(e[0]) for e in self.session.query(Issue.id).all())

        for version in self.jira.getVersions(self.auth, self.project_name) + [None]:
            if version and version.releaseDate is not None:
                release_date = self.jira_con.to_datetime(version.releaseDate)
            else:
                release_date = None

            if version and versions and not version.name in versions:
                continue

            if version:
                version_model = self.session.query(Version).get(version.id)
                if version_model:
                    if version_model.archived and not versions:
                        logger.info("Skipping archived version %s", version.name)
                        continue
                    if version.archived:
                        logger.info("Archiving version %s", version.name)
                        version_model.archived = True
                else:
                    version_model = Version(id=int(version.id), name=version.name,
                        release_date=release_date, archived=version.archived)
                    self.session.add(version_model)
                    self.session.flush()

                active_versions.append(version_model)
            else:
                version_model = None

            logger.info("Cloning issues for version %s", version.name if version else '-')

            if version:
                issues = self.jira.getIssuesFromJqlSearch(self.auth,
                    "project = %s and fixVersion = '%s'" % (self.project_name, version.name),
                    self.jira_con.int_arg(1000))
                version_issues = set(int(e[0]) for e in self.session.query(Issue.id)\
                            .filter(Issue.fix_version == version_model))
            else:
                issues = self.jira.getIssuesFromJqlSearch(self.auth,
                    "project = %s and fixVersion is EMPTY" % self.project_name,
                    self.jira_con.int_arg(1000))
                version_issues = set(int(e[0]) for e in self.session.query(Issue.id)\
                            .filter(Issue.fix_version == None))

            for issue in issues:
                if version:
                    issue_versions = sorted(issue.fixVersions, lambda v1, v2: \
                        int(v2.id) - int(v1.id))
                    if issue_versions[0].name != version.name:
                        continue

                existing_issue = int(issue.id) in existing_issues
                if existing_issue:
                    if int(issue.id) in version_issues:
                        version_issues.remove(int(issue.id))
                    issue_model = self.update_issue(version_model, issue)
                else:
                    issue_model = self.create_issue(version_model, issue)

                for worklog in self.jira.getWorklogs(self.auth, issue.key):
                    if existing_issue:
                        # Weird thing: SUDS based client returns arrays instead of simple attrs
                        if isinstance(worklog.id, list):
                            print "Issue:", issue
                            print "Weird worklog:", worklog
                            sys.exit(1)
                        worklog_model = self.session.query(Worklog).get(int(worklog.id))
                    else:
                        worklog_model = None

                    if not worklog_model:
                        worklog_model = Worklog(id=int(worklog.id))

                    worklog_model.created_at=self.jira_con.to_datetime(worklog.created)
                    worklog_model.author=worklog.author
                    worklog_model.time_spent=worklog.timeSpentInSeconds
                    worklog_model.issue=issue_model

                    self.session.merge(worklog_model)

            for issue_id in version_issues:
                issue = self.session.query(Issue).get(issue_id)
                logger.info("Removing issue %s deleted from version %s", issue.key,
                    version.name if version else 'Unscheduled')
                self.session.delete(issue)

            self.session.commit()

        for version in (active_versions if versions else active_versions + [None]):
            logger.info("Updating issues hierarchy for version %s", version.name if version else '-')

            if version:
                issues = self.session.query(Issue)\
                    .filter(and_(Issue.subtask == False, Issue.fix_version == version))
            else:
                issues = self.session.query(Issue)\
                    .filter(and_(Issue.subtask == False, Issue.fix_version == None))

            for issue in issues:

                    subtasks = self.jira.getIssuesFromJqlSearch(self.auth,
                        'parent = "%s"' % issue.key, self.jira_con.int_arg(100))
                    for subtask in subtasks:
                        try:
                            subtask_model = self.session.query(Issue).filter(Issue.key == subtask.key).one()
                            subtask_model.parent = issue
                        except NoResultFound:
                            logger.warn("Can't find subtask %s of task %s", subtask.key, issue.key)

        self.session.commit()

def main():
    logging.root.addHandler(logging.StreamHandler())
    logging.root.setLevel(logging.DEBUG)
    logging.getLogger('suds').setLevel(logging.INFO)

    versions = None
    if len(sys.argv) > 1:
        versions = sys.argv[1:]
    crawler = JiraCrawler()
    crawler.update_statuses()
    crawler.update_issues_and_worklogs(versions)

if __name__ == '__main__':
    main()
