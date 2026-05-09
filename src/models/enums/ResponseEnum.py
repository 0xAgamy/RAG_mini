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

    PROJECT_NOT_FOUND= "project_not_found"
    INSERT_INTO_VECTOR_DB_ERROR= "insert_into_vector_db_error"
    INSERT_INTO_VECTOR_DB_SUCCESS= "insert_into_vector_db_success"

    VECTOR_DB_COLLECTION_RETRIEVED="vectordb_collection_retrieved"

    VECTOR_SEARCH_SUCCESS="vector_search_success"
    VECTOR_SEARCH_ERROR="vector_search_error"

    RAG_ANSWER_ERROR= "rag_answer_error"
    RAG_ANSWER_SUCCESS= "rag_answer_success"


