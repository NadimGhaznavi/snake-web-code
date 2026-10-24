"""Explicit public event and simulation configuration contracts."""

EVENT_LABELS = {
    ('SnakeLab', 'simulation_completed'): 'Simulation Completed',
    ('Configuration', 'golden_config_retained'): 'Golden Retained',
    ('Conversation', 'prompt_sent'): 'Prompt',
    ('Conversation', 'reply_received'): 'Response',
    ('SnakeLab', 'simulation_submitted'): 'Simulation Submitted',
}

# Numeric fields from Snake Lab's simulation-config-v2 schema.
CONFIGURATION_FIELDS = (
    ('epochs', ('epochs',), 'integer'),
    ('seed', ('seed',), 'integer'),
    ('game_board_width', ('game', 'board_width'), 'integer'),
    ('game_board_height', ('game', 'board_height'), 'integer'),
    ('game_initial_snake_length', ('game', 'initial_snake_length'), 'integer'),
    ('game_max_moves_multiplier', ('game', 'max_moves_multiplier'), 'integer'),
    ('game_rewards_food', ('game', 'rewards', 'food'), 'integer'),
    ('game_rewards_wall', ('game', 'rewards', 'wall'), 'integer'),
    ('game_rewards_snake', ('game', 'rewards', 'snake'), 'integer'),
    ('game_rewards_max_moves', ('game', 'rewards', 'max_moves'), 'integer'),
    ('game_rewards_empty', ('game', 'rewards', 'empty'), 'integer'),
    ('game_rewards_closer_to_food', ('game', 'rewards', 'closer_to_food'), 'integer'),
    ('game_rewards_further_from_food', ('game', 'rewards', 'further_from_food'), 'integer'),
    ('model_hidden_size', ('model', 'hidden_size'), 'integer'),
    ('model_layers', ('model', 'layers'), 'integer'),
    ('model_dropout', ('model', 'dropout'), 'number'),
    ('training_sequence_length', ('training', 'sequence_length'), 'integer'),
    ('training_batch_size', ('training', 'batch_size'), 'integer'),
    ('training_replay_max_frames', ('training', 'replay_max_frames'), 'integer'),
    ('training_learning_rate', ('training', 'learning_rate'), 'number'),
    ('training_gamma', ('training', 'gamma'), 'number'),
    ('training_tau', ('training', 'tau'), 'number'),
    ('training_max_gradient_norm', ('training', 'max_gradient_norm'), 'number'),
    ('epsilon_initial', ('epsilon', 'initial'), 'number'),
    ('epsilon_minimum', ('epsilon', 'minimum'), 'number'),
    ('epsilon_decay', ('epsilon', 'decay'), 'number'),
)
