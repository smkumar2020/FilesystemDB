import os
import mysqlglobals as gl
import dbman

def cd_main():    
    cd_query = "SELECT name FROM tree WHERE parentid = " + str(gl.current_fid)
    print(cd_query)
    output = dbman.query_execute(cd_query)
    for row in output:
        print("file/folder name = ", row[0])

