import os
import ConfigParser
import SOAPpy

class JiraConnection(object):
    def __init__(self):
        config = ConfigParser.SafeConfigParser()
        config.read(os.path.expanduser('~/.jira'))
        jira_url = config.get('default', 'uri')
        jira_user = config.get('default', 'username')
        jira_pass = config.get('default', 'password')
        self.project_name = config.get('default', 'project')
        self.soap = SOAPpy.WSDL.Proxy(jira_url)
        self.auth = self.soap.login(jira_user, jira_pass)
