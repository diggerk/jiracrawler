#!/usr/bin/env python -W ignore::DeprecationWarning

import sys

import logging

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from jiracrawler.model import Base, Version, Issue, Worklog, Status
from jirareports.common import JiraConnection


logger = logging.getLogger(__name__)
logging.root.addHandler(logging.StreamHandler())
logging.root.setLevel(logging.DEBUG)
logging.getLogger('suds').setLevel(logging.INFO)


engine = create_engine('mysql://root:@localhost/xcom_jira', echo=False)
engine.connect()

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)


#jira_con = JiraConnection()
jira_con = JiraConnection(provider='SOAPpy')
(auth, jira, project_name) = (jira_con.auth, jira_con.service, jira_con.project_name)

project = jira.getProjectByKey(auth, project_name)

issue_types = {}
for t in jira.getSubTaskIssueTypesForProject(auth, project.id):
    issue_types[t.id] = t
for t in jira.getIssueTypesForProject(auth, project.id):
    issue_types[t.id] = t

session = Session()

statuses = {}
for status in jira.getStatuses(auth):
    s = Status(id=int(status.id), name=status.name)
    s = session.merge(s)
    statuses[s.id] = s

active_versions = []

versions = None
if len(sys.argv) > 1:
    versions = sys.argv[1:]

for version in jira.getVersions(auth, project_name) + [None]:
    if not version and versions:
        continue

    if version and version.releaseDate is not None:
        release_date = jira_con.to_datetime(version.releaseDate)
    else:
        release_date = None

    if versions and not version.name in versions:
        continue

    if version:
        version_model = session.query(Version).get(version.id)
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
            session.add(version_model)
            session.flush()

        active_versions.append(version_model)

    logger.info("Cloning issues for version %s", version.name if version else '-')

    if version:
        issues = jira.getIssuesFromJqlSearch(auth,
            "project = %s and fixVersion = '%s'" % (project_name, version.name),
            jira_con.int_arg(1000))
        existing_issues = set(int(e[0]) for e in session.query(Issue.id)\
            .filter(Issue.fix_version == version_model))
    else:
        issues = jira.getIssuesFromJqlSearch(auth,
            "project = %s and fixVersion is EMPTY" % project_name,
            jira_con.int_arg(1000))
        existing_issues = set(int(e[0]) for e in session.query(Issue.id)\
            .filter(Issue.fix_version == None))

    for issue in issues:
        existing_issue = int(issue.id) in existing_issues
        if existing_issue:
            existing_issues.remove(int(issue.id))
            issue_model = session.query(Issue).get(int(issue.id))
        else:
            issue_model = Issue(id=int(issue.id))

        issue_model.key=issue.key
        issue_model.type=issue_types[issue.type].name
        issue_model.subtask=issue_types[issue.type].subTask
        issue_model.summary=issue.summary
        issue_model.assignee=issue.assignee
        issue_model.created_at=jira_con.to_datetime(issue.created)
        issue_model.status = statuses[int(issue.status)]
        if version:
            issue_model.fix_version = version_model
        else:
            issue_model.fix_version = None

        if issue.duedate:
            issue_model.due_date = jira_con.to_datetime(issue.duedate)

        issue_model = session.merge(issue_model)

        for worklog in jira.getWorklogs(auth, issue.key):
            if existing_issue:
                if isinstance(worklog.id, list): # Weird thing: SUDS based client returns arrays instead of simple attrs
                    print "Issue:", issue
                    print "Weird worklog:", worklog
                    sys.exit(1)
                worklog_model = session.query(Worklog).get(int(worklog.id))
            else:
                worklog_model = None

            if not worklog_model:
                worklog_model = Worklog(id=int(worklog.id))

            worklog_model.created_at=jira_con.to_datetime(worklog.created)
            worklog_model.author=worklog.author
            worklog_model.time_spent=worklog.timeSpentInSeconds
            worklog_model.issue=issue_model

            session.merge(worklog_model)

    for issue_id in existing_issues:
        issue = session.query(Issue).get(issue_id)
        logger.info("Removing deleted issue: %s", issue.key)
        session.delete(issue)

session.commit()


for version in (active_versions if versions else active_versions + [None]):
    logger.info("Updating issues hierarchy for version %s", version.name if version else '-')

    if version:
        issues = session.query(Issue)\
            .filter(and_(Issue.subtask == False, Issue.fix_version == version))
    else:
        issues = session.query(Issue)\
            .filter(and_(Issue.subtask == False, Issue.fix_version == None))

    for issue in issues:

            subtasks = jira.getIssuesFromJqlSearch(auth, 'parent = "%s"' % issue.key, jira_con.int_arg(100))
            for subtask in subtasks:
                try:
                    subtask_model = session.query(Issue).filter(Issue.key == subtask.key).one()
                    subtask_model.parent = issue
                except NoResultFound:
                    logger.warn("Can't find subtask %s of task %s", subtask.key, issue.key)

session.commit()
