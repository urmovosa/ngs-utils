###################################################################
#
# Molgenis python api client. 
#
####################################################################

import requests
import json
import re
import os.path
from molgenis_api import security
import time
import logging
from datetime import datetime
import copy
import timeit
import urllib
class Connect_Molgenis():
    """This class only has __enter__ and __exit__ function to force use of with statement. This way the passwords saved to file can be cleaned up"""
    def __init__(self, server_url, remove_pass_file = True, new_pass_file = True, password_location = '~',log_file = 'molgenis.log', logging_level='DEBUG', logfile_mode = 'w', profile=True):
        """Pass all args and kwargs to the actual Connection class in __enter__()"""
        self.server_url = server_url
        self.remove_pass_file = remove_pass_file
        self.new_pass_file = new_pass_file
        self.password_location = password_location
        self.log_file = log_file
        self.logging_level = logging_level
        self.logfile_mode = logfile_mode
        self.profile = profile
    def __enter__(self):
        self.enter = True
        class Connection():
            """Actual Class with functionallity. Some simple methods for adding, updating and retrieving rows from Molgenis though the REST API
            BELOW IS OUTDATED DOCS
        
            Args:
                  server_url (string): The url to the molgenis server
                
            Example:
                from molgenis_api import molgenis
                # make a connection
                with open molgenis.Connect_Molgenis()('http://localhost:8080') as connection:
                    # add a row to the entity public_rnaseq_Individuals
                    connection.add_entity_row('public_rnaseq_Individuals',{'id':'John Doe','age':'26', 'gender':'Male'})
                    # get the rows from public_rnaseq_Individuals where gender = Male
                    print connection.get('public_rnaseq_Individuals',[{'field':'gender', 'operator':'EQUALS', 'value':'Male'}])['items'] 
                    # update row in public_rnaseqIndivduals where id=John Doe -> set gender to Female
                    connection.update_entity_row('public_rnaseq_Individuals',[{'field':'id', 'operator':'EQUALS', 'value':'John Doe'}], {'gender':'Female'})  
            """
        
            def __init__(self, server_url, remove_pass_file = True, new_pass_file = True, password_location = '~',log_file = 'molgenis.log', logging_level='DEBUG', logfile_mode = 'w'):
                '''Initialize Python api to talk to Molgenis Rest API
                
                Args:
                    server_url (string):         The url to the molgenis server (ex: https://molgenis39.target.rug.nl/)
                    remove_pass_file (bool):     If True, remove the files containing the passwords after usage (def: True)
                    new_pass_file (str):         If file with password was not removed after last run, but still want to use a new password this run, set to True. Otherwise uses same password as last run (def: False)
                    password_location (string):  Folder where to put the password files in (def: ~)
                    log_file (string):           Path to write logfile with debug info etc to (def: molgenis.log)
                    logging_level (string):      The level of logging to use. See Python's `logging` manual for info on levels (def: DEBUG)
                    logfile_mode (string):       Mode of writing to logfile, e.g. w for overwrite or a for append, see `logging` manual for more details (def: w)
                '''
                # because errors in the __init__ function will not go to __exit__, make sure to clean up after error
                try:
                    # if no path is specified in the log_file name, it should be written in the same location where the script is called from,
                    # not from the location molgenis is located
                    if not os.sep in log_file:
                        log_file = os.getcwd()+os.sep+log_file
                    else:
                        # if there is a path in log_file, make sure that the folder exists
                        if not os.path.exists(os.path.dirname(log_file)):
                            raise OSError('Folder "'+str(os.path.dirname)+'" for writing the molgenis.log file does not exist, change log_file location')
                    logging.basicConfig(filename = log_file, filemode = logfile_mode)
                    logging.getLogger().addHandler(logging.StreamHandler())
                    self.logger = logging.getLogger(__name__)
                    self.logger.setLevel(level=getattr(logging, logging_level))
                    self.login_time = None
                    self.saved_arguments = None
                    self.time_start = timeit.default_timer()
                    security.overwrite_passphrase_location(password_location)
                    if new_pass_file:
                        self.remove_pass_file = True
                        security.remove_secrets_file()
                    security.require_username('Username')
                    security.require_password('Password')
                    self.api_v1_url = server_url+'/api/v1'
                    self.api_v2_url = server_url+'/api/v2'
                    self._construct_login_header()
                    self.entity_meta_data = {}
                    self.column_meta_data = {}
                    self.added_rows = 0
                    self.added_files = 0
                    self.remove_pass_file = remove_pass_file
                except:
                    self.remove_password_files()
                    raise
            
            def _construct_login_header(self):
                '''Log in to the molgenis server and use the retrieve loginResponse token to construct the login header.
                 
                Args:
                    user (string): Login username
                    password (string): Login password
            
                Returns:
                    header (dict): Login header for molgenis server
                '''
                self.session = requests.Session()
                data = json.dumps({'username': security.retrieve('Username'), 'password': security.retrieve('Password')})
                self.logger.debug('Trying to log in with data from '+str(security.PASSPHRASE_FILE) +' to: '+str(self.api_v1_url)+'/login/ with username: '+'*'*len(security.retrieve('Username'))+' password: '+'*'*len(security.retrieve('Password')))
                server_response = self.session.post( self.api_v1_url+'/login/',
                                               data=data, headers={'Content-Type':'application/json'} )
                try:
                    self.check_server_response(server_response, 'retrieve token',url_used=self.api_v1_url+'/login/')
                except Exception as e:
                    if 'Unknown entity [login]' in str(e):
                        # check if http should be https or visa versa, otherwise try adding https:// in front
                        if self.api_v1_url.startswith('https://'): 
                            self.logger.debug('Replacing https:// with http:// in api_v1_url: '+str(self.api_v1_url))
                            self.api_v1_url = self.api_v1_url.lstrip('https://')
                            self.api_v1_url = 'http://'+self.api_v1_url
                        elif self.api_v1_url.startswith('http://'): 
                            self.logger.debug('Replacing http:// with https:// in api_v1_url: '+str(self.api_v1_url))
                            self.api_v1_url = self.api_v1_url.lstrip('http://')
                            self.api_v1_url = 'https://'+self.api_v1_url
                        else:
                            self.logger.debug('Adding https:// to api_v1_url: '+str(self.api_v1_url))
                            self.api_v1_url = 'https://'+self.api_v1_url
                        self.logger.debug('Trying to log in with data from '+str(security.PASSPHRASE_FILE) +' to: '+str(self.api_v1_url)+'/login/ with username: '+'*'*len(security.retrieve('Username'))+' password: '+'*'*len(security.retrieve('Password')))
                        server_response = requests.post( self.api_v1_url+'/login/',
                                                   data=data, headers={'Content-Type':'application/json'} )
                        self.check_server_response(server_response, 'retrieve token',url_used=self.api_v1_url+'/login/')
                    else:
                        raise
                headers = {'Content-type':'application/json', 'x-molgenis-token': server_response.json()['token'], 'Accept':'application/json'}
                self.session.headers.update(headers)
                self.login_time = timeit.default_timer()
                return headers

            def logout(self):
                server_response = self.session.get(self.api_v1_url+'/logout/')
                self.check_server_response(server_response, 'logout')
                return server_response
            
            def check_server_response(self, server_response, type_of_request, entity_used=None, data_used=None,query_used=None,column_used=None,url_used=None):
                '''Retrieve error message from server response
                
                Args:
                    server_response (server response object): Response from server
                    type_of_request (string): Extra info to print with verbose print (def: '')
                Returns:
                    True if response 200 or 201, False if other response, raises error if 400
                    
                Raises:
                    Exception: if json object of server response contains error messages 
                '''
                def error(server_response):
                    try:
                        server_response_json = server_response.json()
                        error_message = str(server_response)+' -> '+server_response.reason+'\n'
                        if 'errors' in server_response_json:
                            if data_used:
                                if not ('Bad Request' in error_message):
                                    error_message += 'Used data: '+str(data_used)+'\n'
                            if entity_used:
                                error_message += 'Used Entity: '+str(entity_used)+'\n'
                            if query_used:
                                error_message += 'Used Query: '+str(query_used)+'\n'
                            if column_used:
                                error_message += 'Used column: '+str(column_used)+'\n'
                            for error in server_response_json['errors']:
                                error_message += error['message']+'\n'
                                # bug in error response when wrong enum value. Remove wrong part of message and add sensible one 
                                # This should be obsolete as wrong error message has been fixed in the api, can be removed after testing
                                if 'Invalid enum value' in error_message:
                                    column_name = re.search('for attribute \'(.+?)\'', error_message).group(1)
                                    entity_name = re.search('of entity \'(.+?)\'', error_message).group(1)
                                    column_meta = self.get_column_meta_data(entity_name,column_name)
                                    enum_options = ', '.join(column_meta['enumOptions'])
                                    error_message = error_message.replace('Value must be less than or equal to 255 characters',
                                                          ' The enum options are: '+enum_options)
                                self.logger.error(error_message.rstrip('\n'))
                                raise Exception(error_message.rstrip('\n'))
                        return server_response_json
                    except ValueError:
                        self.logger.debug(str(server_response)+' -> '+server_response.reason)
                        pass # no json oobject in server_response
                # if service unavailable, try again in 5 minutes
                if str(server_response) == '<Response [503]>':
                    self.logger.debug(str(server_response)+' -> '+server_response.reason+'\n')
                    self.logger.debug('Try again in 5 minutes')
                    time.sleep(300)
                    if self.saved_arguments[0] == 'add_rows':
                        self.add(self.saved_arguments[1:])
                    elif self.saved_arguments[0] == 'add_file':
                        self.add_file(self.saved_arguments[1:])
                    else:
                        self.logger.error(self.saved_arguments[0]+' Not a function')
                if str(server_response) == '<Response [400]>':
                    error(server_response)
                    self.logger.debug(server_response.text)
                    raise Exception(server_response.text)
                elif str(server_response) == '<Response [404]>':
                    error(server_response)
                    error_message = 'Page not found'
                    if url_used:
                        error_message += ' '+str(url_used)
                    self.logger.error(error_message)
                    raise Exception(error_message)
                elif str(server_response) == '<Response [401]>':
                    self.logger.error(type_of_request+' -> '+str(server_response)+' - '+server_response.reason +' (Wrong username - password combination)')
                    raise Exception(type_of_request+' -> '+str(server_response)+' - '+server_response.reason +' (Wrong username - password combination)')
                elif str(server_response) == '<Response [200]>' or str(server_response) == '<Response [201]>' or str(server_response) == '<Response [204]>':
                    message = type_of_request+' -> '+str(server_response)+' - '+server_response.reason 
                    if 'Add row to entity' in type_of_request:
                        message += '. Total added rows this session: '+str(self.added_rows)
                    elif 'Add a file' in type_of_request:
                        message += '. Total added files this session: '+str(self.added_files)
                    self.logger.debug(message)
                    return True
                else:
                    error(server_response)
                    # i didn't go through all response codes, so if it's a different response than expected I only want to raise exception if 
                    # there are error messages in the response object, otherwise just warn that there is a different response than expected
                    self.logger.warning('Expected <Response [200]>, <Response 201> or <Response 204>, got '+str(server_response)+'\nReason: '+server_response.reason)
                    return False
                            
            def validate_data(self, entity_name, data):
                '''Validate that the right column names are given, since otherwise if wrong columns are used it will create empty rows. 
                Only the column names and auto ID get checked, not value type, as server will raise an error if wrong type is tried to be inserted
                
                Args:
                    data (dict): Dictonary that will be used as json_data
                    
                Raises:
                    Exception
                '''
                columns_to_insert = list(data.keys())
                columns_in_entity = self.get_column_names(entity_name)
                difference = set(columns_to_insert).difference(set(columns_in_entity))
                if len(difference) > 0:
                    error_message = 'Provided data has columns which are not in the entity. The wrong columns are: '+', '.join(difference)+'\n'\
                                   +'The provided data is: '+str(data)+'\n'\
                                   +'The entity '+entity_name+' contains the columns: '+', '.join(columns_in_entity)
                    self.logger.error(error_message)
                    raise Exception(error_message)
                entity_id_attribute = self.get_id_attribute(entity_name)
                if entity_id_attribute in data and self.get_column_meta_data(entity_name,entity_id_attribute)['auto']:
                    self.logger.warning('The ID attribute ('+entity_id_attribute+') of the entity ('+entity_name+') you are adding a row to is set to `auto`.\n'\
                                 +'The value you gave for id ('+str(data[entity_id_attribute])+') will not be used. Instead, the ID will be a random string.')
        
            def _sanitize_data(self, data, add_datetime, datetime_column, added_by, added_by_column):
                if add_datetime:
                    data[datetime_column] = str(datetime.now())
                if added_by:
                    data[added_by_column] = security.retrieve('Username')
                # make all values str and remove if value is None or empty string
                data = {k: v for k, v in list(data.items()) if v!=None}
                data = dict([a, str(x)] for a, x in data.items() if len(str(x).strip())>0)
                return data
                        
            def _add_or_file_server_response(self, entity_name, data, server_response, add_type, api_version='v2',ignore_duplicates=False):
                '''Add datetime and added by to entity row or file row
                
                entity_name (string): Name of the entity
                data (dict): data that was added
                server_resonse (obj): Server response object
                add_type (string): Either entity_row or file'''
                if add_type == 'entity_row': 
                    message = time.strftime('%H:%M:%S', time.gmtime(timeit.default_timer()-self.time_start))+ '-' + time.strftime('%H:%M:%S', time.gmtime(timeit.default_timer()-self.login_time))+ ' - Add row to entity '+entity_name
                elif add_type == 'file':
                    message = time.strftime('%H:%M:%S', time.gmtime(timeit.default_timer()-self.login_time))+ ' - Add a file to '+entity_name
                else:
                    raise ValueError('add_type can only be entity_row or file')
                try:
                    self.check_server_response(server_response, message, entity_used=entity_name, data_used=json.dumps(data))
                    if api_version == 'v1':
                        try:
                            added_id = server_response.headers['location'].split('/')[-1]
                        except KeyError:
                            self.logger.debug('Server response header:\n'+str(server_response.headers))
                            raise
                        return added_id
                    elif api_version == 'v2':
                        # return list of IDs
                        try:
                            added_ids = server_response.json()['location'].split('in=(')[1].split(')')[0].replace('"','').split(',')
                        except KeyError:
                            self.logger.debug('server response json:\n'+str(server_response.json()))
                            raise
                        return added_ids
                    else:
                        raise ValueError('That api version does not exist: '+str(api_version))
                except Exception as e:
                    if 'Duplicate value' in str(e) and ignore_duplicates:
                        message = 'Duplicate value not added, instead return id of already existing row'
                        self.logger.debug(message)
                        unique_attributes = re.findall("Duplicate value '(\S+?)' for unique attribute '(\S+?)'", str(e))
                        added_ids = []
                        for unique_att in unique_attributes:
                            query = [{'field':unique_att[1], 'operator':'EQUALS', 'value':unique_att[0]}]
                            if unique_att[1] == self.get_id_attribute(entity_name):
                                added_id = unique_att[0]
                            else:
                                row = self.get(entity_name, query = query)['items'][0]
                                added_id = row[self.get_id_attribute(entity_name)]
                            # v1 only returns 1 ID
                            if api_version == 'v1':
                                return added_id
                            added_ids.append(added_id)
                            if not added_id:
                                raise Exception('No results found with query:')
                            self.logger.debug('id found for row with duplicate value: '+str(added_id))
                        message = '# of added_ids: '+str(len(added_ids))+'\n# of rows in data_list:'+str(len(data))+'\n'
                        if len(added_ids) < len(data):
                            message += 'Not enough IDs for the amount of data provided'
                            self.logger.debug(message)
                            raise ValueError(message) 
                        elif len(added_ids) > len(data):
                            message += 'Too many IDs for the amount of data provided'
                            self.logger.debug(message)
                            raise ValueError(message) 
                        else:
                            return added_ids
                    else:
                        raise
                raise Exception('Code logic broken, check _add_or_file_server_response function')
              
            _add_datetime_default = False
            _added_by_default = False
            _add_datetime_default = False
            _added_by_default = False
            def add(self, entity_name, data_list, validate_json=False, add_datetime=None, datetime_column='datetime_added', added_by=None, added_by_column='added_by',ignore_duplicates=False):
                '''Add one or multiple rows to an entity
                
                Args:
                    entity_name (string): Name of the entity where row should be added
                    data_list (list): List of dicts with Key = column name, value = column value
                    validate_json (bool): If True, check if the given data keys correspond with the column names of entity_name. (def: False)
                    add_datetime (bool): If True, add a datetime to the column <datetime_column> (def: False)
                    datetime_column (str): column name where to add datetime
                    added_by (bool): If true, add the login name of the person that updated the record
                    added_by_column (string): column name where to add name of person that updated record
                    
                Returns:
                    added_ids (list): List of IDs of the rows that got added
                    
                Example:
                    >>> with Connect_Molgenis('https://localhoost:8080') as connection:
                    >>>     print (connection.add('EntityName',[{'column_A':'row 1','column_B', 'row 1'},{'column_A':'row 2','column_B':'row 2'}])
                    >>> with Connect_Molgenis('https://localhoost:8080') as connection:
                    >>>>     print (connection.add('EntityName',{'column_A':'row 1','column_B', 'row 1'})
                    AAAACUGUI6T5KJXRMQK476QAAE
                    
                '''
                if not isinstance(data_list,list) and not isinstance(data_list,dict):
                    raise TypeError('data_list should be of type list or dict')
                elif not isinstance(data_list,list):
                    data_list = [data_list]
                if len(data_list) == 0:
                    raise ValueError('data_list is an empty list, needs to contain a dictionary')
                if not add_datetime:
                    add_datetime = self._add_datetime_default
                if not added_by:
                    added_by = self._added_by_default
                if timeit.default_timer()-self.login_time > 15*60:
                    # molgenis login head times out after a certain time, so after 30 minutes resend login request
                    self._construct_login_header()
                if validate_json:
                    for data in data_list:
                        self.validate_data(entity_name, data)
                # need to save previous input incase service is unavailable, so that we can retry later
                self.saved_arguments = ['add_rows', entity_name, data_list, validate_json, add_datetime, datetime_column,added_by,added_by_column,ignore_duplicates]
                sanitized_data_list = [self._sanitize_data(data, add_datetime, datetime_column, added_by, added_by_column) for data in data_list]
                request_url = self.api_v2_url+'/'+entity_name+'/'
                # post to the entity with the json data
                server_response = self.session.post(request_url, data=json.dumps({"entities":sanitized_data_list}))
                self.added_rows += len(sanitized_data_list)
                added_ids = self._add_or_file_server_response(entity_name, data_list, server_response,'entity_row','v2',ignore_duplicates=ignore_duplicates)
                return added_ids
            def add_file(self, file_path, description, entity_name, extra_data=None, file_name=None, add_datetime=False, datetime_column='datetime_added', added_by=None, added_by_column='added_by', io_stream = None,ignore_duplicates=False):
                '''Add a file to entity File.
                
                Args:
                    file_path (string): Path to the file to be uploaded
                    description (description): Description of the file
                    entity (string): Name of the entity to add the files to
                    data (dict): If extra columns have to be added, provide a dict with key column name, value value (def: None)
                    file_name (string): Name of the file. If None is set to basename of filepath (def: None)
                    added_by (bool): If true, add the login name of the person that updated the record (def: False)
                    added_by_column (string): column name where to add name of person that updated record (def: added_by)
                    add_datetime (bool): If true, add the datetime that the file was added (def: False)
                    add_datetime_column (string): column name where to add datetime (def: datetime_added)
                    io_stream (bytes): Send a file like object to use instead of file path
                Returns:
                    file_id (string): ID if the file that got uploaded (for xref)
                    
                Example:
                    >>> from molgenis_api import molgenis
                    >>> with open molgenis.Connect_Molgenis('http://localhost:8080') as connection:
                            print connection.add_file('/Users/Niek/UMCG/test/data/ATACseq/rundir/QC/FastQC_0.sh')
                    AAAACTWVCYDZ6YBTJMJDWXQAAE
                '''
                if not add_datetime:
                    add_datetime = self._add_datetime_default
                if not added_by:
                    added_by = self._added_by_default
                self.saved_arguments = ['add_file', file_path, description, entity_name, extra_data, file_name, add_datetime, datetime_column,added_by,added_by_column,io_stream,ignore_duplicates]
                file_post_header = copy.deepcopy(self.session.headers)
                old_header = copy.deepcopy(self.session.headers)
                del(file_post_header['Accept'])
                del(file_post_header['Content-type'])
                self.session.headers = file_post_header
                data = {'description': description}
                if extra_data:
                    data.update(extra_data)
                data = self._sanitize_data(data, add_datetime, datetime_column, added_by, added_by_column)
                if io_stream:
                    server_response = self.session.post(self.api_v1_url+'/'+entity_name, 
                                                    files={'attachment':(os.path.basename(file_path), io_stream)},
                                                    data=data)
                else:
                    if not file_name:
                        file_name = os.path.basename(file_path)
                    if not os.path.isfile(file_path):
                        self.logger.error('File not found: '+str(file_path))
                        raise IOError('File not found: '+str(file_path))
                    server_response = self.session.post(self.api_v1_url+'/'+entity_name, 
                                            files={'attachment':(os.path.basename(file_path), open(file_path,'rb'))},
                                            data=data)

                self.added_files += 1
                self.session.headers = old_header
                added_id = self._add_or_file_server_response(entity_name, data, server_response,'file', api_version='v1',ignore_duplicates=ignore_duplicates)
                return added_id
            
            def pretty_print_request(self,req):
                """For debugging purposes
                
                At this point it is completely built and ready
                to be fired; it is "prepared".
            
                However pay attention at the formatting used in 
                this function because it is programmed to be pretty 
                printed and may differ from the actual request.
                """
                self.logger.debug('{}\n{}\n{}\n\n{}'.format(
                    '-----------START-----------',
                    req.method + ' ' + req.url,
                    '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
                    req.params,
                ))
               
            def get(self, entity_name, query=None,attributes=None, num=100, start=0, sortColumn=None, sortOrder=None):
                '''Get row(s) from entity with a query
                
                Args:
                    entity_name (string): Name of the entity where get query should be run on
                    query (list): List of dictionaries with as keys:values -> [{'field':column name, 'operator':'EQUALS', 'value':value}]
                    attributes (?): Attributes to return
                    num (int): Number of results to return
                    start (int): Page to start returning results from
                    sortColumn (string): Column name to sort on
                    sortOrder (string): ORder to sort in
                Returns:
                    result (dict): json dictionary of retrieve data
                '''
                if num > 10000:
                    self.logger.error('Too many rows requested, can not request more than 10000')
                    raise ValueError('Too many rows requested, can not request more than 10000')
                if query:
                    if len(query) == 0:
                        self.logger.error('Can\'t search with empty query')
                        raise ValueError('Can\'t search with empty query')
                    json_query = json.dumps({'q':query})
                    server_response = self.session.post(self.api_v1_url+'/'+urllib.parse.quote_plus(entity_name), data = json_query,
                                                    params={"_method":"GET", "attributes":attributes, "num": num, "start": start, "sortColumn":sortColumn, "sortOrder": sortOrder},)
                    self.check_server_response(server_response, 'Get rows from entity',entity_used=entity_name, query_used=json_query)
                else:
                    req = requests.Request('GET',self.api_v1_url+'/'+urllib.parse.quote_plus(entity_name),headers=self.session.headers,
                                                    params={"attributes":attributes, "num": num, "start": start, "sortColumn":sortColumn, "sortOrder": sortOrder})
                    prepared = req.prepare()
                    server_response = self.session.send(prepared)
                    self.pretty_print_request(req)
                    self.check_server_response(server_response, 'Get rows from entity',entity_used=entity_name)
                server_response_json = server_response.json()
                if server_response_json['total'] >= num:
                    self.logger.warning(str(server_response_json['total'])+' number of rows selected. Max number of rows to retrieve data for is set to '+str(num)+'.\n'
                                +str(num-server_response_json['total'])+' rows will not be in the results.')
                    self.logger.info('Selected '+str(server_response_json['total'])+' row(s).')
                self.logger.debug('query used: '+str(query)+'\n'+
                                  'searching entity: '+str(entity_name)+'\n'+
                                  'returned '+str(len(server_response_json['items']))+' items')
                return server_response_json
          
            _updated_by_default = False
            def update_entity_rows(self, entity_name, data, row_id = None, query_list=None, add_datetime=None, datetime_column='datetime_last_updated', updated_by = None, updated_by_column='updated_by', validate_json=False):
                '''Update an entity row, either by giving the attribute id name and the id for the row to update, or a query for which row to update
            
                Args:
                    entity_name (string): Name of the entity to update
                    data (dict):  Key = column name, value = column value
                    id_attribute: The id_attribute name for the entity which you want to update the row
                    row_id: The row id value (from id_attribute)
                    query_list (list): List of dictionaries which contain query to select the row to update (see documentation of get())  (def:None)
                    add_datetime (bool): If true, add datetime to the column datetime_column (def: False)
                    updated_by (bool): If true, add the login name of the person that updated the record (def: False)
                    datetime_column (string): Column name where to add datetime to if update_by=True (def: datetime_column)
                    updated_by_column (string): column name where to add name of person that updated record (def: updated_by)
                    validate_json (bool): If True, check if the given data keys correspond with the column names of entity_name. (def: False)
                '''
                data = self._sanitize_data(data, add_datetime, datetime_column, updated_by, updated_by_column)
                id_attribute = self.get_id_attribute(entity_name)
                if not add_datetime:
                    add_datetime = self._add_datetime_default
                if not updated_by:
                    updated_by = self._updated_by_default
                if validate_json:
                    self.validate_data(entity_name, data)
                server_response_list = [] 
                if row_id:
                    if query_list:
                        logging.warn('Both row_id and query_list set, will use only row_id')
                    for key in data:
                        server_response = self.session.put(self.api_v1_url+'/'+entity_name+'/'+str(row_id)+'/'+key, data='"'+data[key]+'"')
                        self.check_server_response(server_response, 'Update entity: %s, attribute: %s' % (entity_name,id_attribute),data_used=[self.api_v1_url+'/'+entity_name+'/'+str(row_id)+'/'+key, '"'+data[key]+'"'],entity_used=entity_name)                
                        server_response_list.append(server_response)
                    return server_response_list
                elif query_list:
                    queries = []
                    for query in query_list:
                        queries.append(self._sanitize_data(query, False, False, False, False))
                    entity_data = self.get(entity_name, queries)
                    if len(entity_data['items']) == 0:
                        self.logger.error('Query returned 0 results, no row to update.')
                        raise Exception('Query returned 0 results, no row to update.')
                    for entity_item in entity_data['items']:
                        for key in data:
                            server_response = self.session.put(self.api_v1_url+'/'+entity_name+'/'+str(entity_item[str(id_attribute)])+'/'+key, data='"'+data[key]+'"')
                            server_response_list.append(server_response)
                            self.check_server_response(server_response, 'Update entity: %s, attribute: %s' % (entity_name,id_attribute), query_used=queries,data_used=[self.api_v1_url+'/'+entity_name+'/'+str(entity_item[str(id_attribute)])+'/'+key, '"'+data[key]+'"'],entity_used=entity_name)                
                    return server_response_list
                else:
                    raise ValueError('update_entity_rows function called without setting either row_id or query_list (one of the two needed to know which row to update)')
        
            def get_entity_meta_data(self, entity_name):
                '''Get metadata from entity
                
                Args:
                    entity_name (string): Name of the entity to get meta data of
                
                Returns:
                    result (dict): json dictionary of retrieve data
                '''
                if entity_name in self.entity_meta_data:
                    return self.entity_meta_data[entity_name]
                server_response = self.session.get(self.api_v1_url+'/'+entity_name+'/meta')
                self.check_server_response(server_response, 'Get meta data of entity',entity_used=entity_name)
                entity_meta_data = server_response.json()
                self.entity_meta_data[entity_name] = entity_meta_data
                return entity_meta_data
        
            def get_column_names(self, entity_name):
                '''Get the column names from the entity
                
                Args:
                    entity_name (string): Name of the entity to get column names of
                Returns:
                    meta_data(list): List with all the column names of entity_name
                '''
                entity_meta_data = self.get_entity_meta_data(entity_name)
                attributes = entity_meta_data['attributes']
                return list(attributes.keys())
            
            def get_id_attribute(self, entity_name):
                '''Get the id attribute name'''
                entity_meta_data = self.get_entity_meta_data(entity_name)
                return entity_meta_data['idAttribute']
            
            def get_column_meta_data(self, entity_name, column_name):
                '''Get the meta data for column_name of entity_name
                
                Args:
                    entity_name (string): Name of the entity 
                    column_name (string): Name of the column
                Returns:
                    List with all the column names of entity_name
                '''
                if entity_name+column_name in self.column_meta_data:
                    return self.column_meta_data[entity_name+column_name]
                server_response = self.session.get(self.api_v1_url+'/'+entity_name+'/meta/'+column_name)
                self.check_server_response(server_response, 'Get meta data of column',entity_used=entity_name,column_used=column_name)
                column_meta_data = server_response.json()
                self.column_meta_data[entity_name+column_name] = column_meta_data
                return column_meta_data
            
            def get_column_type(self, entity_name, column_name):
                column_meta_data = self.get_column_meta_data(entity_name, column_name)
                return column_meta_data['fieldType']
        
            def get_all_entity_data(self):
                '''Get info of all entities 
                '''
                raise NotImplementedError('Not implemented yet, returns a max number (~450ish) entities, so if more entities are present (e.g. many packages available), not all entities are returned')
                server_response = self.session.get(self.api_v1_url+'/entities/')
                self.check_server_response(server_response, 'Get info from all entities')
                return server_response
            
            def delete_all_rows_of_all_entities(self, package):
                '''Delete all entities of package
                
                Args:
                    package (string): Package for which to delete all entities. (def: None)
                '''
                if not package:
                    self.logger.error('package can\'t be None, is '+str(package))
                    raise AttributeError('package can\'t be None, is '+str(package))
                server_response = self.get_all_entity_data()
                for entity in server_response.json()['items']:
                    entity_name = entity['fullName']
                    if package in entity_name and not bool(entity['abstract']):
                        self.logger.info('Deleting all rows from',entity_name)
                        try:
                            self.delete_all_entity_rows(entity_name)
                        except Exception as e:
                            self.logger.warning(str(e))
            
            def delete_all_entity_rows(self,entity_name):
                '''delete all entity rows'''
                entity_data = self.get(entity_name,num=10000)
                server_response_list = []
                while len(entity_data['items']) > 0:
                    server_response_list.extend(self.delete_entity_data(entity_data,entity_name))
                    entity_data = self.get(entity_name,num=10000)
                return server_response_list
            
            def delete_entity_rows(self, entity_name, query):
                '''delete entity rows
            
                Args:
                    entity_name (string): Name of the entity to update
                    query (list): List of dictionaries which contain query to select the row to update (see documentation of get())
                '''
                entity_data = self.get(entity_name, query)
                if len(entity_data['items']) == 0:
                    self.logger.error('Query returned 0 results, no row to delete.')
                    raise Exception('Query returned 0 results, no row to delete.')
                return self.delete_entity_data(entity_data, entity_name, query_used=query)
        
            def delete_entity_data(self, entity_data,entity_name,query_used=None):
                '''delete entity data
                
                Args:
                    entity_data (dict): A dictionary with at least key:"items", value:<dict with column IDs>. All items in this dict will be deleted
                    entity_name (string): Name of entity to delete from
                    query_used (string): Incase entity_data was made with a query statement, the query used can be given for more detailed error prints (def: None)
                '''
                server_response_list = []
                id_attribute = self.get_id_attribute(entity_name)
                for rows in entity_data['items']:
                    row_id = rows[id_attribute]
                    server_response = self.session.delete(self.api_v1_url+'/'+entity_name+'/'+str(row_id)+'/')
                    self.check_server_response(server_response, 'Delete entity row',entity_used=entity_name,query_used=query_used)
                    server_response_list.append(server_response)
                return server_response_list
            
            def remove_password_files(self):
                if self.remove_pass_file:
                    security.remove_secrets_file()
                
        self.molgenis_connection_obj = Connection(self.server_url,
                                                  remove_pass_file = self.remove_pass_file,
                                                  new_pass_file = self.new_pass_file,
                                                  password_location = self.password_location,
                                                  log_file = self.log_file,
                                                  logging_level = self.logging_level,
                                                  logfile_mode = self.logfile_mode)
        return self.molgenis_connection_obj
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.molgenis_connection_obj.remove_password_files()

