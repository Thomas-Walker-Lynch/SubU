
/*
  The subu server command line interface.

  Usage:
    server [-s <socket_path>] [-l <log_path>] [arguments...]

  Options:
    -s <socket_path>  Specify the Unix socket file path. Default: ./socket
    -l <log_path>     Specify the log file path. Default: ./log.txt
*/

#define IFACE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "Hello.lib.c"

// Define defaults
#define DEFAULT_SOCKET_PATH "socket"

int main( int argc ,char **argv ){
  char *socket_path = DEFAULT_SOCKET_PATH;
  int error_flag = 0;

  int opt;
  while( (opt = getopt(argc ,argv ,":s:l:")) != -1 ){
    switch( opt ){
      case 's':
        socket_path = optarg;
        break;
      case '?': // Unknown option
        fprintf( stderr ,"%s::main unknown option '-%c'\n" ,argv[0] ,optopt );
        error_flag = 1;
        break;
      case ':': // Missing argument
        fprintf( stderr ,"%s::main missing argument for option '-%c'\n" ,argv[0] ,optopt );
        error_flag = 1;
        break;
    }
  }

  if( optind > argc ){
    fprintf( stderr ,"%s::main optind(%d) > argc(%d), which indicates an option parsing bug\n" ,argv[0] ,optind ,argc );
    error_flag = 1;
  }

  // Exit on error after processing all options
  if( error_flag ){
    fprintf( stderr ,"%s::main usage: %s [-s <socket_path>] [arguments...]\n" ,argv[0] ,argv[0] );
    return EXIT_FAILURE;
  }

  // Rebase argv to prepare for run
  if(optind > 0){
    argv[optind - 1] = argv[0]; // Program name at the new base
    argc -= (optind - 1);
    argv += (optind - 1);
  }

  // Log parsed options
  printf( "%s::main socket_path='%s'\n" ,argv[0] ,socket_path );

  // Call the hello function
  return Hello·run(argc ,argv ,socket_path);
}
