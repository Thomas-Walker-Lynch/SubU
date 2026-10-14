#ifndef IFACE
#define Server·IMPLEMENTATION
#define IFACE
#endif

#ifndef Server·IFACE
#define Server·IFACE

  #include <stdio.h>
  #include <time.h>

  // Exit codes
  typedef enum {
    Server·EXIT_SUCCESS = 0,
    Server·EXIT_LOG_FILE_ERROR,
    Server·EXIT_SOCKET_CREATION_ERROR,
    Server·EXIT_BIND_ERROR,
    Server·EXIT_LISTEN_ERROR,
    Server·EXIT_ACCEPT_ERROR
  } Server·ExitCode;

  // Interface prototypes
  int Server·run( int argc ,char **argv ,int *fds ,char *socket_path );
  void Server·return_condition_report( Server·ExitCode code ,int *fds );
  void Server·report( int *fds ,const char *message );
  FILE* Server·open_log( const char *log_path );

#endif // Server·IFACE

#ifdef Server·IMPLEMENTATION

  // Implementation-specific includes
  #include <sys/socket.h>
  #include <sys/un.h>
  #include <stddef.h>
  #include <sys/types.h>
  #include <bits/socket.h>  // Ensure full definition of struct ucred
  #include <stdlib.h>
  #include <string.h>
  #include <unistd.h>
  #include <errno.h>

  // Constants
  #define Server·BUFFER_SIZE 256
  #define MAX_ARGC 16

  // Internal function prototypes
  static void parse( int *fds ,struct ucred *client_cred ,char *input_line );
  static void hello( int *fds ,int argc ,char *argv[] ,struct ucred *client_cred );

  // Log a message with time and to multiple destinations
  void Server·report( int *fds ,const char *message ){
    time_t now = time(NULL);
    char time_buffer[32];
    strftime(time_buffer ,sizeof(time_buffer) ,"%Y-%m-%dT%H:%M:%SZ" ,gmtime(&now));

    for( int i = 0; fds[i] != -1; ++i ){
      dprintf( fds[i] ,"\n%s:: %s" ,time_buffer ,message );
    }
  }

  int Server·run( int argc ,char **argv ,int *fds ,char *socket_path ){
    (void)argc; // Suppress unused variable warnings
    (void)argv;

    int server_fd ,client_fd;
    struct sockaddr_un address;

    // Create socket
    if( (server_fd = socket(AF_UNIX ,SOCK_STREAM ,0)) == -1 ){
      Server·report(fds ,"Socket creation failed.");
      return Server·EXIT_SOCKET_CREATION_ERROR;
    }

    // Configure socket address
    memset(&address ,0 ,sizeof(address));
    address.sun_family = AF_UNIX;
    strncpy(address.sun_path ,socket_path ,sizeof(address.sun_path) - 1);

    unlink(socket_path);
    if( bind(server_fd ,(struct sockaddr *)&address ,sizeof(address)) == -1 ){
      Server·report(fds ,"Binding socket failed.");
      close(server_fd);
      return Server·EXIT_BIND_ERROR;
    }

    if( listen(server_fd ,5) == -1 ){
      Server·report(fds ,"Listening on socket failed.");
      close(server_fd);
      return Server·EXIT_LISTEN_ERROR;
    }

    char startup_message[Server·BUFFER_SIZE];
    snprintf(startup_message ,Server·BUFFER_SIZE ,"Server running with socket '%s' ,awaiting connections..." ,socket_path);
    Server·report(fds ,startup_message);

    while( (client_fd = accept(server_fd ,NULL ,NULL)) != -1 ){
      struct ucred client_cred;
      socklen_t len = sizeof(client_cred);

      if( getsockopt(client_fd ,SOL_SOCKET ,SO_PEERCRED ,&client_cred ,&len) == -1 ){
        Server·report(fds ,"Failed to retrieve client credentials.");
        close(client_fd);
        continue;
      }

      char connection_message[Server·BUFFER_SIZE];
      snprintf(connection_message ,Server·BUFFER_SIZE ,
               "Connection from PID=%d ,UID=%d ,GID=%d" ,
               client_cred.pid ,client_cred.uid ,client_cred.gid);
      Server·report(fds ,connection_message);

      char buffer[Server·BUFFER_SIZE];
      memset(buffer ,0 ,Server·BUFFER_SIZE);
      ssize_t bytes_read = read(client_fd ,buffer ,Server·BUFFER_SIZE - 1);
      if(bytes_read > 0){
        char *line = strtok(buffer ,"\n");
        while(line != NULL){
          parse(fds ,&client_cred ,line);
          line = strtok(NULL ,"\n");
        }
      } else if(bytes_read == -1){
        Server·report(fds ,"Error reading from client.");
      }

      close(client_fd);
    }

    Server·report(fds ,"Error accepting connection.");
    close(server_fd);
    unlink(socket_path);
    return Server·EXIT_ACCEPT_ERROR;
  }

  // Parse a single input line and dispatch to the appropriate command
  static void parse( int *fds ,struct ucred *client_cred ,char *input_line ){
    char *argv[MAX_ARGC + 1] = {0};
    int argc = 0;

    char *line_copy = strdup(input_line);
    if(!line_copy){
      Server·report(fds ,"Failed to duplicate input line.");
      return;
    }

    char *token = strtok(line_copy ," ");
    while(token != NULL && argc < MAX_ARGC){
      argv[argc++] = token;
      token = strtok(NULL ," ");
    }

    if(argc > 0){
      if( strcmp(argv[0] ,"hello") == 0 ){
        hello(fds ,argc ,argv ,client_cred);
      }else{
        char unknown_command_message[Server·BUFFER_SIZE];
        snprintf(unknown_command_message ,Server·BUFFER_SIZE ,"Unknown command '%s'" ,argv[0]);
        Server·report(fds ,unknown_command_message);
      }
    }

    free(line_copy);
  }

  // Example command: hello
  static void hello( int *fds ,int argc ,char *argv[] ,struct ucred *client_cred ){
    char hello_message[Server·BUFFER_SIZE];
    snprintf(hello_message ,Server·BUFFER_SIZE ,
             "hello:: invoked by PID=%d ,UID=%d ,GID=%d" ,
             client_cred->pid ,client_cred->uid ,client_cred->gid);
    Server·report(fds ,hello_message);

    for( int i = 1; i < argc; ++i ){
      char argument_message[Server·BUFFER_SIZE];
      snprintf(argument_message ,Server·BUFFER_SIZE ,"  Arg %d: %s" ,i ,argv[i]);
      Server·report(fds ,argument_message);
    }
  }

  // Error reporting function
  void Server·return_condition_report( Server·ExitCode code ,int *fds ){
    const char *message;
    switch( code ){
      case Server·EXIT_SUCCESS:
        message = "Operation completed successfully.";
        break;
      case Server·EXIT_LOG_FILE_ERROR:
        message = "Failed to open log file.";
        break;
      case Server·EXIT_SOCKET_CREATION_ERROR:
        message = "Socket creation failed.";
        break;
      case Server·EXIT_BIND_ERROR:
        message = "Binding socket failed.";
        break;
      case Server·EXIT_LISTEN_ERROR:
        message = "Listening on socket failed.";
        break;
      case Server·EXIT_ACCEPT_ERROR:
        message = "Error accepting connection.";
        break;
      default:
        message = "Unknown error occurred.";
        break;
    }

    Server·report(fds ,message);
  }

  // Log file opener
  FILE* Server·open_log( const char *log_path ){
    FILE *log_file = fopen(log_path ,"a+");
    if( log_file ){
      Server·report( (int[]){fileno(log_file), -1} ,"Log file opened.");
    }
    return log_file;
  }

#endif // Server·IMPLEMENTATION
