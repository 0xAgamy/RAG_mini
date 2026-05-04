from enum import Enum

class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS= "file_validated_successfully"
    FILE_TYPE_NOT_SUPPORTED= "file_type_not_supported"
    FILE_SIZE_EXCEEDED= "file_size_exceeded"
    FILE_UPLOADED_SUCCESS= "file_uploaded_successfully" 
    FILE_UPLOADED_FAILED= "file_uploaded_failed"

    PROCESSING_FAILS= "processing_faild"
    PROCESSING_SUCCESS= "processing_success"

    FILE_ID_ERROR= "no_file_found_with_this_id"
    NO_FILES_ERROR= "not_found_files"

