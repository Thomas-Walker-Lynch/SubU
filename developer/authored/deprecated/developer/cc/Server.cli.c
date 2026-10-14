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
#include "Server.lib.c"

// Define defaults
#define DEFAULT_SOCKET_PATH "socket"
#define DEFAULT_LOG_PATH "log.txt"

int main( int argc ,char **argv ){
  char *socket_path = DEFAULT_SOCKET_PATH;
  char *log_path = DEFAULT_LOG_PATH;
  int error_flag = 0;

  // Parse command-line options
  int opt;
  while( (opt = getopt(argc ,argv ,":s:l:")) != -1 ){
    switch( opt ){
      case 's':
        socket_path = optarg;
        break;
      case 'l':
        log_path = optarg;
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
    fprintf( stderr ,"%s::main usage: %s [-s <socket_path>] [-l <log_path>] [arguments...]\n" ,argv[0] ,argv[0] );
    return EXIT_FAILURE;
  }

  // Rebase argv to prepare for run
  if(optind > 0){
    argv[optind - 1] = argv[0]; // Program name at the new base
    argc -= (optind - 1);
    argv += (optind - 1);
  }

  // Open the log file
  FILE *log_file = Server·open_log(log_path);
  if( !log_file ){
    fprintf( stderr ,"%s::main unable to open log file '%s'\n" ,argv[0] ,log_path );
    return Server·EXIT_LOG_FILE_ERROR;
  }

  // Log parsed options
  fprintf( log_file ,"%s::main socket_path='%s'\n" ,argv[0] ,socket_path );
  fprintf( log_file ,"%s::main log_path='%s'\n" ,argv[0] ,log_path );
  fflush(log_file);

  // Prepare file descriptors for error reporting
  int fds[] = { fileno(stderr), fileno(log_file), -1 };

  // Call the core server function
  int exit_code = Server·run(argc ,argv ,fds ,socket_path);

  // Report return condition
  Server·return_condition_report(exit_code ,fds);

  // Clean up
  fclose(log_file);

  return exit_code;
}
