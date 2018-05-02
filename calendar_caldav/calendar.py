# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2016 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
from pytz import timezone
from openerp.exceptions import except_orm, Warning, RedirectWarning
from datetime import datetime, timedelta, time
from time import strptime, mktime, strftime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import re

from openerp import http
from openerp.http import request

from xml.parsers.expat import ExpatError

from pywebdav import lib
from pywebdav.lib.errors import DAV_Error, DAV_NotFound, DAV_Secret
from pywebdav.lib.constants import COLLECTION, OBJECT, DAV_PROPS, RT_ALLPROP, RT_PROPNAME, RT_PROP
from pywebdav.lib import iface

import urlparse


import werkzeug.utils
from werkzeug.http import http_date
from werkzeug import url_encode
import werkzeug

from openerp.service import common


import logging
_logger = logging.getLogger(__name__)


try:
    from icalendar import Calendar, Event, vDatetime, FreeBusy, Alarm
except ImportError:
    raise Warning('icalendar library missing, pip install icalendar')

try:
    import urllib2
except ImportError:
    raise Warning('urllib2 library missing, pip install urllib2')    
    

# calendar_ics -> res.partner

# http://ical.oops.se/holidays/Sweden/-1,+1
# http://www.skatteverketkalender.se/skvcal-manadsmoms-maxfyrtiomiljoner-ingenperiodisk-ingenrotrut-verk1.ics
            
class calendar_event(models.Model):
    _inherit = 'calendar.event'
    
    #~ ics_subscription = fields.Boolean(default=False) # partner_ids + ics_subscription -> its ok to delete

class res_users(models.Model):
    _inherit = 'res.users'
    

    def allowed_cal_items(self,user):
        """Get items from request that user is allowed to access."""
        read_last_collection_allowed = None
        write_last_collection_allowed = None
        read_allowed_items = []
        write_allowed_items = []
        _logger.error('%s %s' % (user,self.env.user))
        return [self.env['calendar.event'].sudo(user=user.id).search([('partner_ids','in',self.partner_id.id)]),self.env['calendar.event'].sudo(user=user.id).search([('user_id','=',self.id)])]

        return [ical.Collection('dav.ics')],[ical.Collection('dav.ics')]

        for item in items:
            if isinstance(item, ical.Collection):
                if rights.authorized(user, item, "r"):
                    log.LOGGER.debug(
                        "%s has read access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    read_last_collection_allowed = True
                    read_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO read access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    read_last_collection_allowed = False

                if rights.authorized(user, item, "w"):
                    log.LOGGER.debug(
                        "%s has write access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    write_last_collection_allowed = True
                    write_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO write access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    write_last_collection_allowed = False
            else:
                # item is not a collection, it's the child of the last
                # collection we've met in the loop. Only add this item
                # if this last collection was allowed.
                if read_last_collection_allowed:
                    log.LOGGER.debug(
                        "%s has read access to item %s" %
                        (user or "Anonymous", item.name))
                    read_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO read access to item %s" %
                        (user or "Anonymous", item.name))

                if write_last_collection_allowed:
                    log.LOGGER.debug(
                        "%s has write access to item %s" %
                        (user or "Anonymous", item.name))
                    write_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO write access to item %s" %
                        (user or "Anonymous", item.name))

        return read_allowed_items, write_allowed_items  
        
        
        



class caldav(http.Controller):
#        http://partner/<res.partner>/calendar/[private.ics|freebusy.ics|public.ics]
     #~ simple_blog_list = request.env['blog.post'].sudo().search([('blog_id', '=', simple_blog.id)], order='message_last_post desc')

    #~ @http.route(['/partner/<model("res.partner"):partner>/calendar/private.ics'], type='http', auth="public", website=True)
    #~ def icalendar_private(self, partner=False, **post):
        #~ if partner:
            #~ document = partner.sudo().get_ics_calendar(type='private').to_ical()
            #~ return request.make_response(
                #~ headers=[('WWW-Authenticate', 'Basic realm="MaxRealm"')]
            #~ )
        #~ else:
            #~ raise Warning("Private failed")
            #~ pass # Some error page

        



    @http.route(['/caldav'], type='http', auth="public", website=True)
    def caldav_icalendar(self, partner=False, **post):
        #~ environ["REQUEST_METHOD"]
        _logger.error('%s %s ' % (request.httprequest.environ['REQUEST_METHOD'],request.httprequest.environ['PATH_INFO']))
        _logger.error('%s  ' % (request.httprequest.environ))
        
        path = request.httprequest.environ.get("PATH_INFO",'')

        # Get function corresponding to method
        function = getattr(self, "do_%s" % request.httprequest.environ["REQUEST_METHOD"].upper())

        # Ask authentication backend to check rights
        try:
            login, password = request.httprequest.environ.get('HTTP_AUTHORIZATION','').lstrip("Basic").strip().decode('base64').split(":")
            _logger.error('user %s password %s ' % (login,password))
        except Exception as e:
            _logger.error('HTTP_AUTH error %s ' % (e))
            return werkzeug.wrappers.Response(status=401,headers=[
                        ('WWW-Authenticate','Basic realm="Kalender"'),
                        ('Server','Odoo %s ' % (common.exp_version().get('server_version'))),
                        ])
        
        user = request.env['res.users'].sudo().search([('login','=',login)],limit=1)
        if user:
            try:
                user.check_credentials(password)
            except:
                _logger.error('Check Credentials %s ' % (login))
                return werkzeug.wrappers.Response(status=403,headers=[
                            ('WWW-Authenticate','Basic realm="Kalender"'),
                            ('Server','Odoo %s ' % (common.exp_version().get('server_version'))),
                            ])
            _logger.error('User OK %s ' % (user))
            content = ''
            status, headers, content = getattr(self, "do_%s" % request.httprequest.environ["REQUEST_METHOD"].upper())(post,user)
            headers.append(('Server','Odoo %s ' % (common.exp_version().get('server_version'))))
            #~ raise Warning(status,headers,content)
            return werkzeug.wrappers.Response(status=status,headers=headers,)
        else:
            raise Warning('Pelle')
        
        
        
        
        

    def do_DELETE(self, content,user):
        """Manage DELETE request."""
        _logger.info('do_delete %s %s' % (content,user))
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        if collection.path == environ["PATH_INFO"].strip("/"):
            # Path matching the collection, the collection must be deleted
            item = collection
        else:
            # Try to get an item matching the path
            name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
            item = collection.items.get(name)

        if item:
            # Evolution bug workaround
            if_match = environ.get("HTTP_IF_MATCH", "*").replace("\\", "")
            if if_match in ("*", item.etag):
                # No ETag precondition or precondition verified, delete item
                answer = xmlutils.delete(environ["PATH_INFO"], collection)
                return client.OK, {}, answer
            else:
                # ETag precondition not verified, do not delete item
                return client.PRECONDITION_FAILED, {}, None

        # No item
        return client.NOT_FOUND, {}, None

    def do_GET(self, environ, read_collections, write_collections, content,
               user):
        """Manage GET request.

        In Radicale, GET requests create collections when the URL is not
        available. This is useful for clients with no MKCOL or MKCALENDAR
        support.

        """
        _logger.info('do_GET %s %s' % (content,user))

        # Display a "Radicale works!" message if the root URL is requested
        if environ["PATH_INFO"] == "/":
            headers = {"Content-type": "text/html"}
            answer = b"<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer

        if not len(read_collections):
            return NOT_ALLOWED

        collection = read_collections[0]

        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)

        if item_name:
            # Get collection item
            item = collection.items.get(item_name)
            if item:
                items = [item]
                if collection.resource_type == "calendar":
                    items.extend(collection.timezones)
                answer_text = ical.serialize(
                    collection.tag, collection.headers, items)
                etag = item.etag
            else:
                return client.NOT_FOUND, {}, None
        else:
            # Create the collection if it does not exist
            if not collection.exists:
                if collection in write_collections:
                    log.LOGGER.debug(
                        "Creating collection %s" % collection.name)
                    collection.write()
                else:
                    log.LOGGER.debug(
                        "Collection %s not available and could not be created "
                        "due to missing write rights" % collection.name)
                    return NOT_ALLOWED

            # Get whole collection
            answer_text = collection.text
            etag = collection.etag

        headers = {
            "Content-Type": collection.mimetype,
            "Last-Modified": collection.last_modified,
            "ETag": etag}
        answer = answer_text.encode(self.encoding)
        return client.OK, headers, answer

    def do_HEAD(self, environ, read_collections, write_collections, content,
                user):
        """Manage HEAD request."""
        _logger.info('do_HEAD %s %s' % (content,user))

        status, headers, answer = self.do_GET(
            environ, read_collections, write_collections, content, user)
        return status, headers, None

    def do_MKCALENDAR(self, environ, read_collections, write_collections,
                      content, user):
        """Manage MKCALENDAR request."""
        
        _logger.info('do_MKCALENDAR %s %s' % (content,user))

        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        props = xmlutils.props_from_request(content)
        timezone = props.get("C:calendar-timezone")
        if timezone:
            collection.replace("", timezone)
            del props["C:calendar-timezone"]
        with collection.props as collection_props:
            for key, value in props.items():
                collection_props[key] = value
            collection.write()
        return client.CREATED, {}, None

    def do_MKCOL(self, environ, read_collections, write_collections, content,
                 user):
        """Manage MKCOL request."""
        
        _logger.info('do_MKCOL %s %s' % (content,user))

        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        props = xmlutils.props_from_request(content)
        with collection.props as collection_props:
            for key, value in props.items():
                collection_props[key] = value
        collection.write()
        return client.CREATED, {}, None

    def do_MOVE(self, environ, read_collections, write_collections, content,
                user):
        """Manage MOVE request."""
        
        _logger.info('do_MOVE %s %s' % (content,user))

        
        if not len(write_collections):
            return NOT_ALLOWED

        from_collection = write_collections[0]

        from_name = xmlutils.name_from_path(
            environ["PATH_INFO"], from_collection)
        if from_name:
            item = from_collection.items.get(from_name)
            if item:
                # Move the item
                to_url_parts = urlparse(environ["HTTP_DESTINATION"])
                if to_url_parts.netloc == environ["HTTP_HOST"]:
                    to_url = to_url_parts.path
                    to_path, to_name = to_url.rstrip("/").rsplit("/", 1)
                    to_collection = ical.Collection.from_path(
                        to_path, depth="0")[0]
                    if to_collection in write_collections:
                        to_collection.append(to_name, item.text)
                        from_collection.remove(from_name)
                        return client.CREATED, {}, None
                    else:
                        return NOT_ALLOWED
                else:
                    # Remote destination server, not supported
                    return client.BAD_GATEWAY, {}, None
            else:
                # No item found
                return client.GONE, {}, None
        else:
            # Moving collections, not supported
            return client.FORBIDDEN, {}, None

    def do_OPTIONS(self, content, user):
        """Manage OPTIONS request."""
        _logger.info('do_OPTIONS %s %s' % (content,user))

        return 200, [
            ("Allow",("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE,OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT")),
            ("DAV","1, 2, 3, calendar-access, addressbook, extended-mkcol")
        ], None

        self.send_response(200)
        self.send_header("Content-Length", 0)

        if self._config.DAV.getboolean('lockemulation'):
            self.send_header('Allow', DAV_VERSION_2['options'])
        else:
            self.send_header('Allow', DAV_VERSION_1['options'])

        self._send_dav_version()

        self.send_header('MS-Author-Via', 'DAV')  # this is for M$
        self.end_headers()



        return 200, [
            ("Allow",("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE,OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT")),
            ("DAV","1, 2, 3, calendar-access, addressbook, extended-mkcol")
        ], None


    def do_PROPFIND(self,content,user):
        """ Retrieve properties on defined resource. """
        _logger.info('do_PROPFIND %s %s' % (content,user))

        dc = DAVInterface('http://localhost/caldav',user)

        # read the body containing the xml request
        # iff there is no body then this is an ALLPROP request
        body = None
        if 'Content-Length' in request.httprequest.headers:
            l = request.httprequest.headers['Content-Length']
            body = content

        #~ uri = urlparse.urljoin(self.get_baseuri(dc), self.path)
        #~ uri = urllib.unquote(uri)

        try:
            pf = lib.propfind.PROPFIND('http://localhost/caldav', dc, request.httprequest.headers.get('Depth', 'infinity'), body)
        except ExpatError:
            # parse error
            return self.send_status(400)

        try:
            DATA = '%s\n' % pf.createResponse()
        except DAV_Error, (ec, dd):
            return self.send_status(ec)

        # work around MSIE DAV bug for creation and modified date
        # taken from Resource.py @ Zope webdav
        if (request.httprequest.headers.get('User-Agent') ==
            'Microsoft Data Access Internet Publishing Provider DAV 1.1'):
            DATA = DATA.replace('<ns0:getlastmodified xmlns:ns0="DAV:">',
                                '<ns0:getlastmodified xmlns:n="DAV:" '
                                'xmlns:b="urn:uuid:'
                                'c2f41010-65b3-11d1-a29f-00aa00c14882/" '
                                'b:dt="dateTime.rfc1123">')
            DATA = DATA.replace('<ns0:creationdate xmlns:ns0="DAV:">',
                                '<ns0:creationdate xmlns:n="DAV:" '
                                'xmlns:b="urn:uuid:'
                                'c2f41010-65b3-11d1-a29f-00aa00c14882/" '
                                'b:dt="dateTime.tz">')


        return 200, [
            ("Allow",("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE,OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT")),
            ("DAV","1, 2, 3, calendar-access, addressbook, extended-mkcol")
        ], 'Hello'
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}

        self.send_body_chunks_if_http11(DATA, 207, 'Multi-Status',
                                        'Multiple responses')



    def Xdo_PROPFIND(self, content,user):
        """Manage PROPFIND request."""
        # Rights is handled by collection in xmlutils.propfind
        
        
        return 200, [
            ("Allow",("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE,OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT")),
            ("DAV","1, 2, 3, calendar-access, addressbook, extended-mkcol")
        ], None
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
            
            
        collections = set(user.allowed_cal_items()[0] + user.allowed_cal_items()[1])
        answer = xmlutils.propfind(
            request.httprequest.environ["PATH_INFO"], content, collections, user)
        return client.MULTI_STATUS, headers, answer

    def do_PROPPATCH(self, environ, read_collections, write_collections,
                     content, user):
        """Manage PROPPATCH request."""
        _logger.info('do_PROPPATCH %s %s' % (content,user))

        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        answer = xmlutils.proppatch(
            environ["PATH_INFO"], content, collection)
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, answer

    def do_PUT(self, environ, read_collections, write_collections, content,
               user):
        """Manage PUT request."""
        _logger.info('do_PUT %s %s' % (content,user))

        
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        collection.set_mimetype(environ.get("CONTENT_TYPE"))
        headers = {}
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
        item = collection.items.get(item_name)

        # Evolution bug workaround
        etag = environ.get("HTTP_IF_MATCH", "").replace("\\", "")
        match = environ.get("HTTP_IF_NONE_MATCH", "") == "*"
        if (not item and not etag) or (
                item and ((etag or item.etag) == item.etag) and not match):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            xmlutils.put(environ["PATH_INFO"], content, collection)
            status = client.CREATED
            # Try to return the etag in the header.
            # If the added item doesn't have the same name as the one given
            # by the client, then there's no obvious way to generate an
            # etag, we can safely ignore it.
            new_item = collection.items.get(item_name)
            if new_item:
                headers["ETag"] = new_item.etag
        else:
            # PUT rejected in all other cases
            status = client.PRECONDITION_FAILED
        return status, headers, None

    def do_REPORT(self, environ, read_collections, write_collections, content,
                  user):
        """Manage REPORT request."""
        _logger.info('do_REPORT %s %s' % (content,user))

        
        if not len(read_collections):
            return NOT_ALLOWED

        collection = read_collections[0]

        headers = {"Content-Type": "text/xml"}

        answer = xmlutils.report(environ["PATH_INFO"], content, collection)
        return client.MULTI_STATUS, headers, answer
        
        
        
        
        if partner:
            #~ raise Warning("Public successfull %s" % partner.get_ics_calendar(type='public').to_ical())
            #~ return partner.get_ics_calendar(type='public').to_ical()
            document = partner.sudo().get_ics_calendar(type='freebusy').to_ical()
            return request.make_response(
                document,
                headers=[
                    ('Content-Disposition', 'attachment; filename="freebusy.ifb"'),
                    ('Content-Type', 'text/calendar'),
                    ('Content-Length', len(document)),
                ]
            )
        else:
            raise Warning()
            pass # Some error page
    
    

class DAVInterface(iface.dav_interface):
    """ 
    Model a Odoo for DAV

    """

    def __init__(self, uri, user,verbose=False):

        # should we be verbose?
        self.verbose = verbose
        self.user = user
        if uri == '/':
            self.parent = None
        else:
            self.parent = DAVInterface('/',user,verbose)
        _logger.info('Initialized with %s %s' % (uri,user))

    def setDirectory(self, path):
        """ Sets the directory """

        #~ if not os.path.isdir(path):
            #~ raise Exception, '%s not must be a directory!' % path

        self.directory = path

    def setBaseURI(self, uri):
        """ Sets the base uri """

        self.baseuri = uri

    def get_davpath(self):
        pass

    def uri2local(self,uri):
        """ map uri in baseuri and local part """

        uparts=urlparse.urlparse(uri)
        fileloc=uparts[2][1:]
        #~ filename=os.path.join(self.directory,fileloc)
        #~ filename=os.path.normpath(filename)
        filename = fileloc
        return filename

    def local2uri(self,filename):
        """ map local filename to self.baseuri """

        pnum=len(split(self.directory.replace("\\","/"),"/"))
        parts=split(filename.replace("\\","/"),"/")[pnum:]
        sparts="/"+joinfields(parts,"/")
        uri=urlparse.urljoin(self.baseuri,sparts)
        return uri


    def get_childs(self, uri, filter=None):
        """ return the child objects as self.baseuris for the given URI """

        fileloc=self.uri2local(uri)
        filelist=[]

        #~ if os.path.exists(fileloc):
            #~ if os.path.isdir(fileloc):
                #~ try:
                    #~ files=os.listdir(fileloc)
                #~ except:
                    #~ raise DAV_NotFound

                #~ for file in files:
                    #~ newloc=os.path.join(fileloc,file)
                    #~ filelist.append(self.local2uri(newloc))

                #~ log.info('get_childs: Childs %s' % filelist)

        return filelist

    def get_data(self,uri, range = None):
        """ return the content of an object """

        path=self.uri2local(uri)
        if os.path.exists(path):
            if os.path.isfile(path):
                file_size = os.path.getsize(path)
                if range == None:
                    fp=open(path,"r")
                    log.info('Serving content of %s' % uri)
                    return Resource(fp, file_size)
                else:
                    if range[1] == '':
                        range[1] = file_size
                    else:
                        range[1] = int(range[1])

                    if range[0] == '':
                        range[0] = file_size - range[1]
                    else:
                        range[0] = int(range[0])

                    if range[0] > file_size:
                        raise DAV_Requested_Range_Not_Satisfiable

                    if range[1] > file_size:
                        range[1] = file_size

                    fp=open(path,"r")
                    fp.seek(range[0])
                    log.info('Serving range %s -> %s content of %s' % (range[0], range[1], uri))
                    return Resource(fp, range[1] - range[0])
            elif os.path.isdir(path):
                # GET for collections is defined as 'return s/th meaningful' :-)
                from StringIO import StringIO
                stio = StringIO('Directory at %s' % uri)
                return Resource(StringIO('Directory at %s' % uri), stio.len)
            else:
                # also raise an error for collections
                # don't know what should happen then..
                log.info('get_data: %s not found' % path)

        raise DAV_NotFound

    def _get_dav_resourcetype(self,uri):
        """ return type of object """
        #~ path=self.uri2local(uri)
        if 'public.ics' in uri or 'private.ics' in uri:
            return OBJECT

        elif uri == '/caldav':
            return COLLECTION

        raise DAV_NotFound

    def _get_dav_displayname(self,uri):
        raise DAV_Secret    # do not show

    def _get_dav_getcontentlength(self,uri):
        """ return the content length of an object """
        path=self.uri2local(uri)
        return '123'
        #~ if os.path.exists(path):
            #~ if os.path.isfile(path):
                #~ s=os.stat(path)
                #~ return str(s[6])

        return '0'

    def get_lastmodified(self,uri):
        """ return the last modified date of the object """
        collection = set(self.user.allowed_cal_items(self.user)).sorted(lambda c: c.start_datetime)
        raise Warning(collection)
        path=self.uri2local(uri)
        if os.path.exists(path):
            s=os.stat(path)
            date=s[8]
            return date

        raise DAV_NotFound

    def get_creationdate(self,uri):
        """ return the last modified date of the object """
        path=self.uri2local(uri)
        return 14020202.0
        if os.path.exists(path):
            s=os.stat(path)
            date=s[9]
            return date

        raise DAV_NotFound

    def _get_dav_getcontenttype(self,uri):
        """ find out yourself! """

        path=self.uri2local(uri)
        return 'text/plain'
        if os.path.exists(path):
            if os.path.isfile(path):
                if MAGIC_AVAILABLE is False \
                        or self.mimecheck is False:
                    return 'application/octet-stream'
                else:
                    ret, encoding = mimetypes.guess_type(path)

                    # for non mimetype related result we
                    # simply return an appropriate type
                    if ret.find('/')==-1:
                        if ret.find('text')>=0:
                            return 'text/plain'
                        else:
                            return 'application/octet-stream'
                    else:
                        return ret

            elif os.path.isdir(path):
                return "httpd/unix-directory"

        raise DAV_NotFound, 'Could not find %s' % path

    def put(self, uri, data, content_type=None):
        """ put the object into the filesystem """
        path=self.uri2local(uri)
        try:
            fp=open(path, "w+")
            if isinstance(data, types.GeneratorType):
                for d in data:
                    fp.write(d)
            else:
                if data:
                    fp.write(data)
            fp.close()
            log.info('put: Created %s' % uri)
        except:
            log.info('put: Could not create %s' % uri)
            raise DAV_Error, 424

        return None

    def mkcol(self,uri):
        """ create a new collection """
        path=self.uri2local(uri)

        # remove trailing slash
        if path[-1]=="/": path=path[:-1]

        # test if file already exists
        if os.path.exists(path):
            raise DAV_Error,405

        # test if parent exists
        h,t=os.path.split(path)
        if not os.path.exists(h):
            raise DAV_Error, 409

        # test, if we are allowed to create it
        try:
            os.mkdir(path)
            log.info('mkcol: Created new collection %s' % path)
            return 201
        except:
            log.info('mkcol: Creation of %s denied' % path)
            raise DAV_Forbidden

    ### ?? should we do the handler stuff for DELETE, too ?
    ### (see below)

    def rmcol(self,uri):
        """ delete a collection """
        path=self.uri2local(uri)
        if not os.path.exists(path):
            raise DAV_NotFound

        try:
            shutil.rmtree(path)
        except OSError:
            raise DAV_Forbidden # forbidden
        
        return 204

    def rm(self,uri):
        """ delete a normal resource """
        path=self.uri2local(uri)
        if not os.path.exists(path):
            raise DAV_NotFound

        try:
            os.unlink(path)
        except OSError, ex:
            log.info('rm: Forbidden (%s)' % ex)
            raise DAV_Forbidden # forbidden

        return 204

    ###
    ### DELETE handlers (examples)
    ### (we use the predefined methods in davcmd instead of doing
    ### a rm directly
    ###

    def delone(self,uri):
        """ delete a single resource

        You have to return a result dict of the form
        uri:error_code
        or None if everything's ok

        """
        return delone(self,uri)

    def deltree(self,uri):
        """ delete a collection 

        You have to return a result dict of the form
        uri:error_code
        or None if everything's ok
        """

        return deltree(self,uri)


    ###
    ### MOVE handlers (examples)
    ###

    def moveone(self,src,dst,overwrite):
        """ move one resource with Depth=0
        """

        return moveone(self,src,dst,overwrite)

    def movetree(self,src,dst,overwrite):
        """ move a collection with Depth=infinity
        """

        return movetree(self,src,dst,overwrite)

    ###
    ### COPY handlers
    ###

    def copyone(self,src,dst,overwrite):
        """ copy one resource with Depth=0
        """

        return copyone(self,src,dst,overwrite)

    def copytree(self,src,dst,overwrite):
        """ copy a collection with Depth=infinity
        """

        return copytree(self,src,dst,overwrite)

    ###
    ### copy methods.
    ### This methods actually copy something. low-level
    ### They are called by the davcmd utility functions
    ### copytree and copyone (not the above!)
    ### Look in davcmd.py for further details.
    ###

    def copy(self,src,dst):
        """ copy a resource from src to dst """

        srcfile=self.uri2local(src)
        dstfile=self.uri2local(dst)
        try:
            shutil.copy(srcfile, dstfile)
        except (OSError, IOError):
            log.info('copy: forbidden')
            raise DAV_Error, 409

    def copycol(self, src, dst):
        """ copy a collection.

        As this is not recursive (the davserver recurses itself)
        we will only create a new directory here. For some more
        advanced systems we might also have to copy properties from
        the source to the destination.
        """

        return self.mkcol(dst)

    def exists(self,uri):
        """ test if a resource exists """
        path=self.uri2local(uri)
        return 1
        if os.path.exists(path):
            return 1
        return None

    def is_collection(self,uri):
        """ test if the given uri is a collection """
        path=self.uri2local(uri)
        if os.path.isdir(path):
            return 1
        else:
            return 0


    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
