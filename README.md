Overview
========

Rationale
---------
JIRA's builtin reporting is often not powerful nor flexible enough to
suit project needs. There are many reporting plugins available but good 
plugins are not free and still all of those are not flexible enough.

In some cases it's just not possible to install plugins into a
JIRA due to corporate policies or the fact that a JIRA instance 
is not under your control at all.

SQL reporting for JIRA
----------------------
This crawler fetches issues and worklogs from JIRA 
via JIRA SOAP API. It's useful to have power of SQL to do any kind of 
ad-hoc reporting.

Database Model
==============
Crawler fetches JIRA versions, issue statuses, issues and worklogs.
This is the database model used to store crawled data.

![Crawler Database Diagram](jiracrawler/raw/master/model.jpg "Crawler Database Diagram")


Configuration
=============
Describe projects you're going to analyze in the file ~/.jira.
Sample configuration:

    [default]
    username=aklochkov
    password=mysecret
    uri=https://issues.mycompany.net/rpc/soap/jirasoapservice-v2?wsdl
    project=INTPRJ
    db_name=intprj_jira
    db_user=jira
    db_pass=secret

    [customer_jira]
    username=aklochkov
    password=asecret
    uri=https://customersite.com/rpc/soap/jirasoapservice-v2?wsdl
    project=TWIX
    db_name=twix_jira
    db_user=jira
    db_pass=secret

Installation and usage
======================
1. Install the crawler into the system:

    sudo python setup.py install 

2. Create a separate MySQL database for each project you're analyzing.
3. Run crawler to clone all versions of a project INTPRJ.

    jira_crawler INTPRJ

4. Later repeat step 3 to fetch updates. Pprovide version name as an 
   additional parameter to clone or update a particular version

    jira_crawler INTPRJ version_1

Sample queries
=============

Amount of work done today per developer
---------------------------------------

    select v.name version, w.author, cast(sum(time_spent) / 3600 as decimal(5,1)) hours from worklog w join issue i on i.id=w.issue_id join version v on v.id=i.fix_version_id where date(w.created_at) = str_to_date('$DATE', '%Y-%m-%d') group by v.name, w.author order by v.release_date, v.name, author;

Work done in a given date range grouped by developer
----------------------------------------------------

    select v.name, author, cast(sum(time_spent)/3600 as decimal(5,1)) hours from worklog w join issue i on i.id=w.issue_id left outer join version v on v.id=i.fix_version_id where date(w.created_at) >= str_to_date('$DATE1', '%Y-%m-%d') and date(w.created_at) <= str_to_date('$DATE2', '%Y-%m-%d') group by v.name, author;

Work done on a given date grouped by top-level tasks
----------------------------------------------------

    select v.name version, i2.key, substring(i2.summary, 1, 40) summary, date, due_date, cast(sum(time_spent) / 3600 as decimal(5,1)) hours, s.name status from (select case subtask when 1 then i.parent_id else i.id end parent, date(w.created_at) date, w.time_spent from worklog w join issue i on i.id=w.issue_id where date(w.created_at) >= str_to_date('$DATE', '%Y-%m-%d')) t1 join issue i2 on i2.id=parent join version v on v.id=i2.fix_version_id join status s on s.id=i2.status_id group by v.name, i2.key, i2.summary, date order by v.release_date, v.name, date, parent;


Automated reporting
===================

One of easy ways to provide automated reports is to create jobs in CI server which fetch the data
from JIRA and generate reports. 
