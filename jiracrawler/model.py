from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer, String,
    Date, DateTime, Boolean)
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declared_attr


class Base(object):

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    __table_args__ = {'mysql_engine': 'InnoDB'}
    __mapper_args__= {'always_refresh': True}


Base = declarative_base(cls=Base)


class Version(Base):
    id =  Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    release_date = Column(Date())
    archived = Column(Boolean, default=False)


class Status(Base):
    id =  Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)


class Issue(Base):
    id =  Column(Integer, primary_key=True)
    key = Column(String(10), nullable=False)
    type = Column(String(20), nullable=False)
    subtask = Column(Boolean, nullable=False)
    summary = Column(String(200), nullable=False)
    assignee = Column(String(20))
    created_at = Column(DateTime(), nullable=False)
    due_date = Column(Date())
    parent_id = Column(Integer, ForeignKey('issue.id'))
    fix_version_id = Column(Integer, ForeignKey('version.id'))
    status_id = Column(Integer, ForeignKey('status.id'), nullable=False)

    subtasks = relationship("Issue", backref=backref("parent", remote_side=[id]))
    fix_version = relationship("Version", backref=backref("issues", order_by=id))
    status = relationship("Status")


class Worklog(Base):
    id =  Column(Integer, primary_key=True)
    created_at = Column(DateTime(), nullable=False)
    author = Column(String(20), nullable=False)
    time_spent = Column(Integer, nullable=False)
    issue_id = Column(Integer, ForeignKey('issue.id'), nullable=False)

    issue = relationship("Issue", backref=backref("worklogs", order_by=id))

