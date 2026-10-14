#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include "Db.lib.c"

int main(int argc ,char *argv[]){
  if( argc < 2 ){
    fprintf(stderr ,"Usage: %s <sqlite_handle_as_hex>\n" ,argv[0]);
    return EXIT_FAILURE;
  }

  // Parse the SQLite handle from the command-line argument
  uintptr_t handle_as_int;
  if( sscanf(argv[1] ,"%lx" ,&handle_as_int) != 1 ){
    fprintf(stderr ,"%s::main failed to parse handle '%s'\n" ,argv[0] ,argv[1]);
    return EXIT_FAILURE;
  }

  sqlite3 *db = (sqlite3 *)handle_as_int;

  // Attempt to close the database
  if( db ){
    Db·close(db);
    printf("Database handle %p closed successfully.\n" ,db);
    return EXIT_SUCCESS;
  } else {
    fprintf(stderr ,"Invalid or NULL database handle: %p\n" ,db);
    return EXIT_FAILURE;
  }
}
