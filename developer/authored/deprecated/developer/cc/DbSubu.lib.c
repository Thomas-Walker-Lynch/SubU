#ifndef IFACE
#define DbSubu·IMPLEMENTATION
#define IFACE
#endif

#ifndef DbSubu·IFACE
#define DbSubu·IFACE

  #include <sqlite3.h>

  typedef struct DbSubu {
    sqlite3 *db;
  } DbSubu;


  // db connection
  DbSubu* DbSubu·open( const char *db_path );
  void DbSubu·close( DbSubu *db );
  int DbSubu·validate_schema( DbSubu *db );

  // User Management
  int DbSubu·add_user( DbSubu *db ,const char *name ,const char *home_directory ,int shell_id ,int parent_id ,int user_type_id );
  int DbSubu·delete_user( DbSubu *db ,int user_id );
  int DbSubu·get_user( DbSubu *db ,int user_id ,char **name ,char **home_directory ,int *shell_id ,int *parent_id ,int *user_type_id );

  // Sharing Management
  int DbSubu·add_share( DbSubu *db ,int user_id ,int other_user_id ,const char *permissions );
  int DbSubu·delete_share( DbSubu *db ,int share_id );

  // System Resource Management
  int DbSubu·grant_resource( DbSubu *db ,int user_id ,int resource_id ,int granted_by );
  int DbSubu·revoke_resource( DbSubu *db ,int user_id ,int resource_id );

  // Event Logging
  int DbSubu·log_event( DbSubu *db ,int event_id ,int user_id );

#endif // DbSubu·IFACE

#ifdef DbSubu·IMPLEMENTATION

  #include <stdio.h>
  #include <stdlib.h>
  #include <string.h>
  #include "Db.lib.c"

  // Open the database
  DbSubu* DbSubu·open( const char *db_path ){
    DbSubu *db = malloc( sizeof(DbSubu) );
    if( !db ){
      fprintf( stderr ,"DbSubu·open:: failed to allocate memory for DbSubu\n" );
      return NULL;
    }
    db->db = Db·open(db_path ,true);
    if( !db->db ){
      free( db );
      return NULL;
    }
    return db;
  }

  // Close the database
  void DbSubu·close( DbSubu *db ){
    if( db ){
      Db·close( db->db );
      free( db );
    }
  }

  // Validate the schema
  int DbSubu·validate_schema( DbSubu *db ){
    // Validation logic for ensuring the schema is correct
    return 0; // Placeholder for schema validation implementation
  }

  // Add a user
  int DbSubu·add_user( DbSubu *db ,const char *name ,const char *home_directory ,int shell_id ,int parent_id ,int user_type_id ){
    char sql[256];
    snprintf
      (
       sql 
       ,sizeof(sql) 
       ,"INSERT INTO user (name ,home_directory ,shell ,parent_id ,user_type_id) VALUES ('%s' ,'%s' ,%d ,%d ,%d);"
       ,name 
       ,home_directory 
       ,shell_id 
       ,parent_id 
       ,user_type_id
      );
    return Db·query( db->db ,sql ,NULL ,NULL );
  }

  // Delete a user
  int DbSubu·delete_user( DbSubu *db ,int user_id ){
    char sql[128];
    snprintf( sql ,sizeof(sql) ,"DELETE FROM user WHERE id = %d;" ,user_id );
    return Db·query( db->db ,sql ,NULL ,NULL );
  }

  // Log an event
  int DbSubu·log_event( DbSubu *db ,int event_id ,int user_id ){
    char sql[128];
    snprintf
      (
       sql 
       ,sizeof(sql) 
       ,"INSERT INTO db_event (event_id ,user_id) VALUES (%d ,%d);"
       ,event_id 
       ,user_id
      );
    return Db·query( db->db ,sql ,NULL ,NULL );
  }

  // Add to a list (private function)
  static int add_to_list( sqlite3 *db ,const char *list_name ,const char *entry_name ){
    char sql[128];
    snprintf
      (
       sql 
       ,sizeof(sql) 
       ,"INSERT INTO %s (name) VALUES ('%s');"
       ,list_name 
       ,entry_name
      );
    return Db·query( db ,sql ,NULL ,NULL );
  }

  // Get list entries (private function)
  static char** get_list( sqlite3 *db ,const char *list_name ,int *count ){
    char sql[128];
    snprintf( sql ,sizeof(sql) ,"SELECT name FROM %s;" ,list_name );

    struct ListResult {
      char **entries;
      int count;
    } result = { NULL ,0 };

    int callback( void *arg ,int argc ,char **argv ,char **col_names ){
      (void)argc; (void)col_names;
      struct ListResult *res = arg;
      res->entries = realloc( res->entries ,(res->count + 1) * sizeof(char *) );
      res->entries[res->count++] = strdup( argv[0] );
      return 0;
    }

    if( Db·query( db ,sql ,callback ,&result ) != SQLITE_OK ){
      for( int i = 0; i < result.count; ++i ){
        free( result.entries[i] );
      }
      free( result.entries );
      return NULL;
    }

    *count = result.count;
    return result.entries;
  }

#endif // DbSubu·IMPLEMENTATION
