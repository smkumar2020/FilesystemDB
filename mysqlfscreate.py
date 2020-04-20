from __future__ import print_function

import os
import mysql.connector
from mysql.connector import errorcode
import dbman
import datetime
from stat import *
import dbman

DB_NAME = 'filesystem'
TABLES_IN_DB = ['tree', 'fattrb', 'fdata', 'link', 'user', 'fgroup', 'usergroup']

DROP_TREE = "DROP TABLE IF EXISTS "+ TABLES_IN_DB[0]
DROP_FATTRB = "DROP TABLE IF EXISTS "+ TABLES_IN_DB[1]
DROP_FDATA = "DROP TABLE IF EXISTS "+ TABLES_IN_DB[2]

TABLES = {}

TABLES['tree'] = (
    "CREATE TABLE `tree` ("
    "`fid` bigint(20) unsigned NOT NULL,"
    "`parentid` bigint(20) unsigned default NULL,"
    "`nodeid` bigint(20) unsigned NOT NULL,"
    "PRIMARY KEY (`fid`),"
    "KEY `parentid` (`parentid`)"
    ") DEFAULT CHARSET=utf8mb4"
    )

TABLES['fattrb'] = (
   "CREATE TABLE `fattrb` ("
   "`nodeid` bigint(20) unsigned NOT NULL,"
   "`name` varchar(255) character set utf8 collate utf8_bin NOT NULL,"
   "`filetype` int(11) NOT NULL default '0',"
   "`uid` int(10) unsigned NOT NULL default '0',"
   "`gid` int(10) unsigned NOT NULL default '0',"
   "`userpm` int(11) NOT NULL default '0',"
   "`grppm` int(11) NOT NULL default '0',"
   "`otherpm` int(11) NOT NULL default '0',"
   "`mtime` timestamp NOT NULL,"
   "`size` bigint(20) NOT NULL default '0',"
   "`nlink` int(10) NOT NULL default '0',"
   "PRIMARY KEY  (`nodeid`)"
   ") DEFAULT CHARSET=utf8mb4"
   )

TABLES['fdata'] = (
   "CREATE TABLE `fdata` ("
   "`nodeid` bigint(20) NOT NULL,"
   "`data` longblob,"
   "PRIMARY KEY  (`nodeid`)"
   ")  DEFAULT CHARSET=binary"
   )

TABLES['link'] = (
   "CREATE TABLE `link` ("
   "`fid` bigint(20) NOT NULL,"
   "`linkfid` bigint(20) NOT NULL,"
   "PRIMARY KEY  (`fid`)"
   ")  DEFAULT CHARSET=utf8mb4"
   )

TABLES['user'] = (
   "CREATE TABLE `user` ("
   "`id` int NOT NULL,"
   "`name` varchar(32) NOT NULL"
   ")  DEFAULT CHARSET=utf8mb4"
   )

TABLES['fgroup'] = (
   "CREATE TABLE `fgroup` ("
   "`id` int NOT NULL,"
   "`name` varchar(32) NOT NULL"
   ")  DEFAULT CHARSET=utf8mb4"
   )

TABLES['usergroup'] = (
   "CREATE TABLE `usergroup` ("
   "`userid` int NOT NULL,"
   "`groupid` int NOT NULL,"
   "PRIMARY KEY  (`userid`, `groupid`)"
   ")  DEFAULT CHARSET=utf8mb4"
   )

add_tree_entry = ("INSERT INTO tree (fid, parentid, nodeid) VALUES (%s, %s, %s)")
add_fattrb_entry = ("INSERT INTO fattrb (nodeid, name, filetype, uid, gid, userpm, grppm, otherpm, mtime, size, nlink) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
add_fdata_entry = ("INSERT INTO fdata (nodeid, data) VALUES (%s, %s)")
add_link_entry = ("INSERT INTO link (fid, linkfid) VALUES (%s, %s)")
add_user_entry = ("INSERT INTO user(id, name) VALUES (%s, %s)")
add_usergroup_entry = ("INSERT INTO usergroup(userid, groupid) VALUES (%s, %s)")
add_group_entry = ("INSERT INTO fgroup(id, name) VALUES (%s, %s)")
add_groupuser_entry = ("INSERT INTO usergroup(userid, groupid)"\
    " VALUES ((SELECT id from user where name = %s), %s)")

fileid = 0
storeinodes = list()
resolvedsoftlinks = list()
def open_database(cnx, cursor, dbname):
    try:
        cursor.execute("USE {}".format(dbname))
        #dbman.get_linkfid_from_linkpath()
        #cnx.commit()
    except mysql.connector.Error as err:
        print("Failed opening database: {}".format(err))
        return 1

def create_database(cnx, cursor, dbname, fspath):
    try:
        cursor.execute(
            "DROP DATABASE IF EXISTS {}".format(dbname))
    except mysql.connector.Error as err:
        print("Failed dropping database :", dbname)
        return 1
    else:
        print("Creating database : {}".format(dbname))

    try:
        cursor.execute(
            "CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(dbname))
    except mysql.connector.Error as err:
        print("Failed creating database: {}".format(err))
        return 1

    # Open database
    if (open_database(cnx, cursor, dbname) == 1):
        return 1

    # Create tables
    for table_name in TABLES:
        table_description = TABLES[table_name]
        try:
            cursor.execute(table_description)
        except mysql.connector.Error as err:
            print(err.msg)
        else:
            print("Creating table : {}".format(table_name))

    # adding root, just for testing, TODO make it proper
    try:    
        cursor.execute("INSERT tree(fid, parentid, nodeid) VALUES(0,0,0)")
        cursor.execute(
            "INSERT fattrb(nodeid, name, filetype, uid, gid, userpm, grppm, otherpm, mtime, size, nlink)"
                " VALUES(0, '/', 16384, 0, 0, 448, 40, 4, CURRENT_TIMESTAMP, 0, 1)")   
        cursor.execute(
            "UPDATE fattrb SET nodeid = 0 WHERE name = '/'")           
    except mysql.connector.Error as err:
        print("Failed inserting value for root : {}".format(err))
        return 1

    # populate data 
    scan_directories(cursor, fspath, 0)
    createUserTable(cursor, fspath)
    createGroupTable(cursor, fspath)

    # TODO creating tree entry for ~, etc.,

    # There will be no update after this point, hence commit
    cnx.commit()

    store_link_ids()
    cnx.commit()

def createUserTable(cursor, path):
    passwdfilepath = path+"/etc/passwd"

    if not os.path.isfile(passwdfilepath):
       print("File path {} does not exist. Exiting...".format(passwdfilepath))
       return 1    
    
    with open(passwdfilepath) as fp:        
        for line in fp:
            #print("contents {}".format(line))
            userentry = line.strip().split(':')           
            #print(userentry)
            try:
                usertableentry = []
                usertableentry.append(userentry[2])
                usertableentry.append(userentry[0])
                cursor.execute(add_user_entry, usertableentry)
            except mysql.connector.Error as err:
                print("Failed creating link table: {}".format(err))
                return 1

            try:
                usergrouptableentry = []
                usergrouptableentry.append(userentry[2])
                usergrouptableentry.append(userentry[3])
                cursor.execute(add_usergroup_entry, usergrouptableentry)
            except mysql.connector.Error as err:
                print("Failed creating link table: {}".format(err))
                return 1            

def createGroupTable(cursor, path):
    groupfilepath = path+"/etc/group"

    if not os.path.isfile(groupfilepath):
       print("File path {} does not exist. Exiting...".format(groupfilepath))
       return 1    
    
    with open(groupfilepath) as fp:        
        for line in fp:
            #print("contents {}".format(line))
            groupentry = line.strip().split(':')
            groupusers = line.strip().rsplit(':', 1)

            #print(groupentry)
            try:
                grouptableentry = []
                grouptableentry.append(groupentry[2])
                grouptableentry.append(groupentry[0])
                cursor.execute(add_group_entry, grouptableentry)
            except mysql.connector.Error as err:
                print("Failed creating group table: {}".format(err))
                return 1
            
            if (groupusers[1] != ""):
                gusplit = groupusers[1].split(',')
                for user in gusplit:
                    try:
                        guentry = []
                        guentry.append(user)
                        guentry.append(groupentry[2])
                        cursor.execute(add_groupuser_entry, guentry)
                    except mysql.connector.Error as err:
                        print("Failed creating usergroup table: {}".format(err))
                        return 1            

def store_softlinks(cursor, fid, nodeid, fentry):
    linkdata = []
    linkdata.append(fid)
    linkdata.append(0)
    cursor.execute(add_link_entry, linkdata)
    
    if nodeid not in storeinodes:
       sfdata = []
       sfdata.append(nodeid)
       linkpath = os.readlink(fentry)
       sfdata.append(linkpath)
       cursor.execute(add_fdata_entry, sfdata)
       
    rsoftlinks = (fid, nodeid, os.path.relpath(os.path.realpath(fentry), os.path.dirname(os.path.abspath(fentry))))
    resolvedsoftlinks.append(rsoftlinks)

def file_data(cursor, nodeid, fentry):
    if nodeid not in storeinodes:
       try:
          file_handle = open(fentry, 'rb')
          file_content = file_handle.read()
          file_handle.close()
       except:
          print('Cannot read '+str(fentry.name))
          file_content = None
       print("file_data ----> start "+ str(fentry.name))
       fdata = []
       fdata.append(nodeid)
       fdata.append(file_content)
       cursor.execute(add_fdata_entry, fdata)
       print("file_data ----> end "+ str(fentry.name))

def f_attributes(cursor, fid, parentid, fname, attr):
    if not attr is None and attr.st_ino not in storeinodes:
       fattrb = []
       fattrb.append(attr.st_ino)
       fattrb.append(fname)
       fattrb.append(S_IFMT(attr.st_mode))
       fattrb.append(attr.st_uid)
       fattrb.append(attr.st_gid)
       fattrb.append(attr.st_mode & S_IRWXU)
       fattrb.append(attr.st_mode & S_IRWXG)
       fattrb.append(attr.st_mode & S_IRWXO)
       #fattrb.append(attr.st_mtime)
       #timestamp_str = datetime.datetime.fromtimestamp(attr.st_mtime).strftime('%Y-%m-%d-%H:%M')
       timestamp_str = datetime.datetime.fromtimestamp(attr.st_mtime).strftime('%Y-%m-%d-%H:%M:%S')
       #print(timestamp_str)
       fattrb.append(timestamp_str)
       fattrb.append(attr.st_size)
       fattrb.append(attr.st_nlink)
       cursor.execute(add_fattrb_entry, fattrb)

def scan_directories(cursor, path, parentid):
    global fileid
    with os.scandir(path) as dir_entries:
        for entry in dir_entries:
            tree_entry = []
            fileid = fileid + 1
            info = None
            
            try:
                info = entry.stat()
            except:
                pass
            
            if info is not None:
                #print('inode is '+str(info.st_ino))
                tree_entry.append(fileid)
                tree_entry.append(parentid)
                tree_entry.append(info.st_ino)
                cursor.execute(add_tree_entry, tree_entry)
                
                f_attributes(cursor, fileid, parentid, entry.name, info)

                if os.path.isdir(entry):  
                   parentid1 = fileid
                   if os.path.islink(entry):
                      store_softlinks(cursor, parentid1, info.st_ino, entry)
                   # stores the inodes of directories
                   storeinodes.append(info.st_ino)
                   fileid = scan_directories(cursor, entry, parentid1)  
                elif os.path.isfile(entry):  
                   if os.path.islink(entry):
                      store_softlinks(cursor, fileid, info.st_ino, entry)
                   else:
                      file_data(cursor, info.st_ino, entry)
                storeinodes.append(info.st_ino)
            else:
                fileid = fileid - 1
    return fileid

def store_link_ids():
    for i in range(len(resolvedsoftlinks)):
        (fid, nodeid, resolvedpath) = resolvedsoftlinks[i]
        dbman.get_linkfid_from_linkpath(fid, nodeid, resolvedpath)    
