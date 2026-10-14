#ifndef IFACE
#define Db·IMPLEMENTATION
#define IFACE
#endif

#ifndef Db·IFACE
#define Db·IFACE

  #include <sqlite3.h>
  #include <stdbool.h>

  // Enum for exit codes
  typedef enum {
    Db·EXIT_SUCCESS = 0,
    Db·EXIT_DB_OPEN_ERROR,
    Db·EXIT_SCHEMA_LOAD_ERROR,
    Db·EXIT_MEMORY_ALLOCATION_ERROR,
    Db·EXIT_STATEMENT_PREPARE_ERROR,
    Db·EXIT_STATEMENT_EXECUTE_ERROR
  } Db·ExitCode;

  // Interface prototypes
  sqlite3* Db·open(const char *db_path ,bool create_if_not_exists);
  Db·ExitCode Db·load_schema(sqlite3 *db, const char *schema_path);
  Db·ExitCode Db·log_event(sqlite3 *db, int event_id, int user_id);
  int Db·query(
    sqlite3 *db 
    ,const char *sql 
    ,int (*callback)(void * ,int ,char ** ,char **) 
    ,void *callback_arg
  );
  void Db·close(sqlite3 *db);

#endif // Db·IFACE

#ifndef Db·IMPLEMENTATION

  #include <sqlite3.h>
  #include <stdio.h>
  #include <stdlib.h>
  #include <string.h>
  #include <errno.h>
  #include <time.h>
  #include <string.h>

  sqlite3* Db·open(const char *db_path ,bool create_if_not_exists){
    sqlite3 *db;
    FILE *file_check = fopen(db_path ,"r");

    if(!file_check && create_if_not_exists){
      file_check = fopen(db_path ,"w");
      if(!file_check){
        fprintf(
          stderr,
          "Db::open failed to create database file '%s': %s\n",
          db_path,
          strerror(errno)
        );
        return NULL;
      }
      fclose(file_check);
      printf("Db::open created new database file '%s'\n", db_path);
    }else if(!file_check){
      fprintf(stderr ,"Db::open database file '%s' not found and create flag not set\n" ,db_path);
      return NULL;
    }else{
      fclose(file_check);
    }

    if( sqlite3_open(db_path ,&db) != SQLITE_OK ){
      fprintf(
        stderr,
        "Db::open failed to open database '%s': %s\n",
        db_path,
        sqlite3_errmsg(db)
      );
      return NULL;
    }

    printf("Db::open database '%s' opened successfully\n", db_path);
    return db;
  }

  // Load schema from a file
  Db·ExitCode Db·load_schema(sqlite3 *db ,const char *schema_path){
    FILE *file = fopen(schema_path, "r");
    if(!file){
      fprintf
        (
         stderr
         ,"Db::load_schema failed to open schema file '%s'\n"
         ,schema_path
         );
      return Db·EXIT_SCHEMA_LOAD_ERROR;
    }

    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    rewind(file);

    char *schema = malloc(file_size + 1);
    if(!schema){
      fprintf(stderr, "Db::load_schema memory allocation failed\n");
      fclose(file);
      return Db·EXIT_MEMORY_ALLOCATION_ERROR;
    }

    fread(schema, 1, file_size, file);
    schema[file_size] = '\0';
    fclose(file);

    char *err_msg = NULL;
    if( sqlite3_exec(db, schema, NULL, NULL, &err_msg) != SQLITE_OK ){
      fprintf
        (
         stderr
         ,"Db::load_schema failed to execute schema: %s\n"
         ,err_msg
         );
      sqlite3_free(err_msg);
      free(schema);
      return Db·EXIT_STATEMENT_EXECUTE_ERROR;
    }

    printf("Db::load_schema schema initialized successfully from '%s'\n", schema_path);
    free(schema);
    return Db·EXIT_SUCCESS;
  }

  // Log an event into the database
  Db·ExitCode Db·log_event(sqlite3 *db ,int event_id ,int user_id){
    const char *sql_template =
      "INSERT INTO db_event (event_time ,event_id ,user_id) "
      "VALUES (CURRENT_TIMESTAMP ,? ,?);";
    sqlite3_stmt *stmt;

    if( sqlite3_prepare_v2(db ,sql_template ,-1 ,&stmt ,NULL) != SQLITE_OK ){
      fprintf
        (
         stderr
         ,"Db::log_event failed to prepare statement: %s\n"
         ,sqlite3_errmsg(db)
         );
      return Db·EXIT_STATEMENT_PREPARE_ERROR;
    }

    sqlite3_bind_int(stmt, 1, event_id);
    sqlite3_bind_int(stmt, 2, user_id);

    if( sqlite3_step(stmt) != SQLITE_DONE ){
      fprintf
        (
         stderr
         ,"Db::log_event failed to execute statement: %s\n"
         ,sqlite3_errmsg(db)
         );
      sqlite3_finalize(stmt);
      return Db·EXIT_STATEMENT_EXECUTE_ERROR;
    }

    sqlite3_finalize(stmt);
    return Db·EXIT_SUCCESS;
  }

  // Query Execution Function
  int Db·query(
    sqlite3 *db 
    ,const char *sql 
    ,int (*callback)(void * ,int ,char ** ,char **) 
    ,void *callback_arg
  ){
    char *err_msg = NULL;
    int rc = sqlite3_exec(db ,sql ,callback ,callback_arg ,&err_msg);

    if( rc != SQLITE_OK ){
      fprintf
        (
         stderr 
         ,"Db::query SQL error: %s\nQuery: %s\n" 
         ,err_msg 
         ,sql
         );
      sqlite3_free(err_msg);
      return rc;
    }

    return SQLITE_OK;
  }

  // Close the database
  void Db·close(sqlite3 *db){
    if( db ){
      sqlite3_close(db);
      printf("Db::close database connection closed\n");
    }
  }

#endif // Db·IMPLEMENTATION


