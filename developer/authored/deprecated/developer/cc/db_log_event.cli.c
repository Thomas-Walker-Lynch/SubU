#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "DbSubu.lib.c"

int main(int argc ,char *argv[]){
  if( argc < 3 ){
    fprintf(stderr, "Usage: %s <db_path> <user_id>\n", argv[0]);
    return 1;
  }

  const char *db_path = argv[1];
  int user_id = atoi(argv[2]);

  DbSubu *db = DbSubu·open(db_path);
  if( !db ){
    fprintf(stderr, "Failed to open database: %s\n", db_path);
    return 1;
  }

  int result = DbSubu·delete_user(db, user_id);
  DbSubu·close(db);

  if( result == 0 ){
    printf("User deleted successfully.\n");
    return 0;
  } else {
    fprintf(stderr, "Failed to delete user.\n");
    return 1;
  }
}
