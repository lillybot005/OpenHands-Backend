import os
import uuid
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.events.action.message import MessageAction
from openhands.experiments.experiment_manager import ExperimentManagerImpl
from openhands.integrations.provider import (
    CUSTOM_SECRETS_TYPE_WITH_JSON_SCHEMA,
    PROVIDER_TOKEN_TYPE,
)
from openhands.integrations.service_types import ProviderType
from openhands.server.data_models.agent_loop_info import AgentLoopInfo
from openhands.server.session.conversation_init_data import ConversationInitData
from openhands.server.shared import (
    ConversationStoreImpl,
    SettingsStoreImpl,
    config,
    conversation_manager,
)
from openhands.server.types import LLMAuthenticationError, MissingSettingsError
from openhands.storage.data_models.conversation_metadata import (
    ConversationMetadata,
    ConversationTrigger,
)
from openhands.utils.conversation_summary import get_default_conversation_title


async def create_new_conversation(
    user_id: str | None,
    git_provider_tokens: PROVIDER_TOKEN_TYPE | None,
    custom_secrets: CUSTOM_SECRETS_TYPE_WITH_JSON_SCHEMA | None,
    selected_repository: str | None,
    selected_branch: str | None,
    initial_user_msg: str | None,
    image_urls: list[str] | None,
    replay_json: str | None,
    conversation_instructions: str | None = None,
    conversation_trigger: ConversationTrigger = ConversationTrigger.GUI,
    attach_convo_id: bool = False,
    git_provider: ProviderType | None = None,
    conversation_id: str | None = None,
) -> AgentLoopInfo:
    logger.info(
        'Creating conversation',
        extra={
            'signal': 'create_conversation',
            'user_id': user_id,
            'trigger': conversation_trigger.value,
        },
    )
    logger.info('Loading settings')
    settings_store = await SettingsStoreImpl.get_instance(config, user_id)
    settings = await settings_store.load()
    logger.info('Settings loaded')

    session_init_args: dict[str, Any] = {}
    if settings:
        session_init_args = {**settings.__dict__, **session_init_args}
        # We could use litellm.check_valid_key for a more accurate check,
        # but that would run a tiny inference.
        if (
            not settings.llm_api_key
            or settings.llm_api_key.get_secret_value().isspace()
        ):
            logger.warning(f'Missing api key for model {settings.llm_model}')
            raise LLMAuthenticationError(
                'Error authenticating with the LLM provider. Please check your API key'
            )

    else:
        # For anonymous users or when settings are not found, create default settings
        logger.info('Settings not present, creating default settings for anonymous user')
        from openhands.storage.data_models.settings import Settings
        from pydantic import SecretStr
        import os
        
        # Create default settings using environment variables
        # For anonymous users, use a mock API key if none is provided
        api_key = os.getenv('LLM_API_KEY') or os.getenv('OPENROUTER_API_KEY') or 'mock-api-key-for-testing'
        
        default_settings = Settings(
            language='en',
            agent=os.getenv('DEFAULT_AGENT', 'CodeActAgent'),
            max_iterations=100,
            llm_model=os.getenv('LLM_MODEL', 'anthropic/claude-3-haiku-20240307'),
            llm_api_key=SecretStr(api_key),
            llm_base_url=os.getenv('LLM_BASE_URL', 'https://openrouter.ai/api/v1'),
            confirmation_mode=False,
            enable_default_condenser=True,
            enable_sound_notifications=False,
            enable_proactive_conversation_starters=True,
        )
        
        logger.info(f'Using default settings for anonymous user with model: {default_settings.llm_model}')
        
        session_init_args = {**default_settings.__dict__, **session_init_args}

    session_init_args['git_provider_tokens'] = git_provider_tokens
    session_init_args['selected_repository'] = selected_repository
    session_init_args['custom_secrets'] = custom_secrets
    session_init_args['selected_branch'] = selected_branch
    session_init_args['git_provider'] = git_provider
    session_init_args['conversation_instructions'] = conversation_instructions
    conversation_init_data = ConversationInitData(**session_init_args)


    logger.info('Loading conversation store')
    conversation_store = await ConversationStoreImpl.get_instance(config, user_id)
    logger.info('ServerConversation store loaded')

    # For nested runtimes, we allow a single conversation id, passed in on container creation
    if conversation_id is None:
        conversation_id = uuid.uuid4().hex

    if not await conversation_store.exists(conversation_id):

        logger.info(
            f'New conversation ID: {conversation_id}',
            extra={'user_id': user_id, 'session_id': conversation_id},
        )

        conversation_init_data = ExperimentManagerImpl.run_conversation_variant_test(user_id, conversation_id, conversation_init_data)
        conversation_title = get_default_conversation_title(conversation_id)

        logger.info(f'Saving metadata for conversation {conversation_id}')
        await conversation_store.save_metadata(
            ConversationMetadata(
                trigger=conversation_trigger,
                conversation_id=conversation_id,
                title=conversation_title,
                user_id=user_id,
                selected_repository=selected_repository,
                selected_branch=selected_branch,
                git_provider=git_provider,
                llm_model=conversation_init_data.llm_model,
            )
        )

    logger.info(
        f'Starting agent loop for conversation {conversation_id}',
        extra={'user_id': user_id, 'session_id': conversation_id},
    )
    initial_message_action = None
    if initial_user_msg or image_urls:
        initial_message_action = MessageAction(
            content=initial_user_msg or '',
            image_urls=image_urls or [],
        )

    if attach_convo_id:
        logger.warning('Attaching convo ID is deprecated, skipping process')

    agent_loop_info = await conversation_manager.maybe_start_agent_loop(
        conversation_id,
        conversation_init_data,
        user_id,
        initial_user_msg=initial_message_action,
        replay_json=replay_json,
    )
    logger.info(f'Finished initializing conversation {agent_loop_info.conversation_id}')
    return agent_loop_info
