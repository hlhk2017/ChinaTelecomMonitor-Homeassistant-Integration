import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN,
    CONF_PHONENUM,
    CONF_PASSWORD,
    CONF_TELECOM_DEVICE_ID,
    CONF_UPDATE_INTERVAL_MINUTES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
)
import re
import logging

_LOGGER = logging.getLogger(__name__) # 添加 logger

UPDATE_INTERVAL_SCHEMA = vol.All(
    vol.Coerce(int),
    vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES),
)


# 验证手机号码的格式
def validate_phone_number(phone):
    pattern = re.compile(r'^\d{11}$')
    if not pattern.match(phone):
        raise vol.Invalid("无效的手机号码，请输入 11 位数字的手机号码")
    return phone


def get_update_interval(config_entry):
    value = (
        config_entry.options.get(CONF_UPDATE_INTERVAL_MINUTES)
        or config_entry.data.get(CONF_UPDATE_INTERVAL_MINUTES)
        or DEFAULT_UPDATE_INTERVAL_MINUTES
    )
    try:
        return max(int(value), MIN_UPDATE_INTERVAL_MINUTES)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL_MINUTES

class ChinaTelecomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChinaTelecomOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                user_input[CONF_PHONENUM] = validate_phone_number(user_input[CONF_PHONENUM])

                # 检查是否已经配置过该手机号码
                await self.async_set_unique_id(user_input[CONF_PHONENUM])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="中国电信", data=user_input
                )
            except vol.Invalid as e:
                errors["base"] = str(e)
                _LOGGER.error(f"配置验证失败: {e}") # 记录错误
            except Exception as e:
                errors["base"] = "配置过程中出现未知错误，请重试"
                _LOGGER.exception("配置过程中出现未知错误") # 记录详细异常信息

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONENUM): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_TELECOM_DEVICE_ID): str,
                    vol.Optional(
                        CONF_UPDATE_INTERVAL_MINUTES,
                        default=DEFAULT_UPDATE_INTERVAL_MINUTES,
                    ): UPDATE_INTERVAL_SCHEMA,
                }
            ),
            errors=errors,
            description_placeholders={"name": "中国电信"}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        try:
            import_config[CONF_PHONENUM] = validate_phone_number(import_config[CONF_PHONENUM])

            await self.async_set_unique_id(import_config[CONF_PHONENUM])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="中国电信 (导入)", data=import_config
            )
        except vol.Invalid as e:
            _LOGGER.error(f"从配置文件导入时出现错误: {str(e)}")
        except Exception as e:
            _LOGGER.error(f"从配置文件导入时出现未知错误: {str(e)}")
        return self.async_abort(reason="import_failed")


class ChinaTelecomOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        telecom_device_id = (
            self._config_entry.options.get(CONF_TELECOM_DEVICE_ID)
            or self._config_entry.data.get(CONF_TELECOM_DEVICE_ID)
            or ""
        )
        update_interval_minutes = get_update_interval(self._config_entry)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TELECOM_DEVICE_ID, default=telecom_device_id): str,
                    vol.Optional(
                        CONF_UPDATE_INTERVAL_MINUTES,
                        default=update_interval_minutes,
                    ): UPDATE_INTERVAL_SCHEMA,
                }
            ),
        )
