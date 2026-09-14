MAX_MESSAGE_LENGTH = 1024 * 1024 * 1024
GRPC_OPTIONS = [
    ('grpc.max_seed_message_length', MAX_MESSAGE_LENGTH),
    ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)
]