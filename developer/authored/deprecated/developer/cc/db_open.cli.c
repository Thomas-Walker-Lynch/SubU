#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Db.lib.c"

// Define default database path
#define DEFAULT_DB_PATH "db.sqlite"

int main(int argc ,char *argv[]){
  const char *db_path = (argc > 1) ? argv[1] : DEFAULT_DB_PATH;

  // Open the database using Db·open
  sqlite3 *db = Db·open(db_path ,true);
  if( !db ){
    fprintf(stderr ,"Failed to open or create database: %s\n" ,db_path);
    return EXIT_FAILURE;
  }

  // Check if the file was created or already existed
  printf("Database %s opened successfully\n" ,db_path);

  // Attempt to close the database
  if( db ){
    Db·close(db);
    printf("Database handle %p closed successfully.\n" ,db);
    return EXIT_SUCCESS;
  } else {
    fprintf(stderr ,"Invalid or NULL database handle: %p\n" ,db);
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
