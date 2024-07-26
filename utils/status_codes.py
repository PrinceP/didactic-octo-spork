class StatusCodes:
    # Task stage
    SUCCESS         = "WSP_000"
    PENDING         = "WSP_001" 
    INPROGRESS      = "WSP_002"
    
    # Client
    INVALID_REQUEST                 =  "WSP_400" # Empty, null, invalid filed in payload
    EXCEEDING_PERMITTED_RESOURCES   = "WSP_401"  # < 300s is permitted
    RESOURCE_DOES_NOT_EXIST         = "WSP_402"  # Can not find melody for exmaple
    UNSUPPORTED                     = "WSP_403"  # Type of resource: melody must be *mp3

    # Server
    TIMEOUT         = "WSP_500" # If a task exceeding timeout => Set status timeout
    ERROR           = "WSP_501" # unknown ERROR
    RABBIT_ERROR    = "WSP_502" # Service cannot connect to Rabbit
    REDIS_ERROR     = "WSP_303" # Service cannot connect to Redis
    S3_ERROR        = "WSP_504" # Service cannot connect to S3