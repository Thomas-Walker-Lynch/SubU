#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "DbSubu.lib.c"

int main(int argc ,char *argv[]){
  if( argc < 7 ){
    fprintf(stderr, "Usage: %s <db_path> <name> <home_directory> <shell_id> <parent_id> <user_type_id>\n", argv[0]);
    return 1;
  }

  const char *db_path = argv[1];
  const char *name = argv[2];
  const char *home_directory = argv[3];
  int shell_id = atoi(argv[4]);
  int parent_id = atoi(argv[5]);
  int user_type_id = atoi(argv[6]);

  DbSubu *db = DbSubu·open(db_path);
  if( !db ){
    fprintf(stderr, "Failed to open database: %s\n", db_path);
    return 1;
  }

  int result = DbSubu·add_user(db, name, home_directory, shell_id, parent_id, user_type_id);
  DbSubu·close(db);

  if( result == 0 ){
    printf("User added successfully.\n");
    return 0;
  } else {
    fprintf(stderr, "Failed to add user.\n");
    return 1;
  }
}
