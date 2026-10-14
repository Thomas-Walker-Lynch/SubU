#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "DbSubu.lib.c"

int main(int argc ,char *argv[]){
  const char *db_path = (argc > 1) ? argv[1] : "db.sqlite";
  DbSubu *db = DbSubu·open(db_path);
  if( !db ){
    fprintf(stderr, "Failed to open database: %s\n", db_path);
    return 1;
  }

  int result = DbSubu·validate_schema(db);
  DbSubu·close(db);

  if( result == 0 ){
    printf("Schema validation passed.\n");
    return 0;
  } else {
    fprintf(stderr, "Schema validation failed.\n");
    return 1;
  }
}
