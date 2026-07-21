import logging
import asyncio

from datetime import timedelta
import uuid
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import (
    DOMAIN,
    CONF_PHONENUM,
    CONF_PASSWORD,
    CONF_DEVICE_ID,
    CONF_LOGIN_INFO,
    CONF_TELECOM_DEVICE_ID,
    CONF_UPDATE_INTERVAL_MINUTES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
)

# 导入 telecom_class
from .telecom_class import Telecom 

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the China Telecom sensors."""
    phonenum = entry.data[CONF_PHONENUM]
    password = entry.data[CONF_PASSWORD]

    # 检查配置项中是否有 device_id，如果没有则生成并保存
    if CONF_DEVICE_ID not in entry.data:
        device_id = str(uuid.uuid4())
        new_data = {**entry.data, CONF_DEVICE_ID: device_id}
        hass.config_entries.async_update_entry(entry, data=new_data)
    else:
        device_id = entry.data[CONF_DEVICE_ID]

    coordinator = ChinaTelecomDataUpdateCoordinator(
        hass, entry, phonenum, password  
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        _LOGGER.error("Failed to fetch initial China Telecom data. Integration will not set up.")
        return

    masked_phonenum = f"{phonenum[:3]}****{phonenum[7:]}"

    sensors = []
    # 余额信息
    sensors.append(ChinaTelecomSensor(coordinator, "balance", f"{masked_phonenum} 电信账户余额", "元", "mdi:cash", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "currentMonthCost", f"{masked_phonenum} 电信本月消费", "元", "mdi:cash-clock", device_id))
    # 流量信息
    sensors.append(ChinaTelecomSensor(coordinator, "flowTotal", f"{masked_phonenum} 流量总量", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "flowUse", f"{masked_phonenum} 流量已用", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "flowBalance", f"{masked_phonenum} 流量剩余", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "flowOver", f"{masked_phonenum} 流量超量", "GB", "mdi:network-off", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "commonTotal", f"{masked_phonenum} 通用流量总量", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "commonUse", f"{masked_phonenum} 通用流量已用", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "commonOver", f"{masked_phonenum} 通用流量超量", "GB", "mdi:network-off", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "specialTotal", f"{masked_phonenum} 专用流量总量", "GB", "mdi:network", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "specialUse", f"{masked_phonenum} 专用流量已用", "GB", "mdi:network", device_id))
    # 流量使用率传感器
    sensors.append(ChinaTelecomSensor(coordinator, "percentUsed", f"{masked_phonenum} 流量使用率", "%", "mdi:percent", device_id))
    
    # 通话信息
    sensors.append(ChinaTelecomSensor(coordinator, "voiceTotal", f"{masked_phonenum} 通话总量", "分钟", "mdi:phone", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "voiceUsage", f"{masked_phonenum} 通话已用", "分钟", "mdi:phone", device_id))
    sensors.append(ChinaTelecomSensor(coordinator, "voiceBalance", f"{masked_phonenum} 通话剩余", "分钟", "mdi:phone", device_id))
    # 通话使用率传感器
    sensors.append(ChinaTelecomSensor(coordinator, "voicePercentUsed", f"{masked_phonenum} 通话使用率", "%", "mdi:percent", device_id))

    # 积分传感器
    sensors.append(ChinaTelecomSensor(coordinator, "points", f"{masked_phonenum} 电信积分", "分", "mdi:trophy", device_id))

    async_add_entities(sensors)


class ChinaTelecomDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching China Telecom data."""

    def __init__(self, hass, entry, phonenum, password): 
        """Initialize."""
        self.phonenum = phonenum
        self.password = password
        self.entry = entry
        self.telecom_device_id = (
            entry.options.get(CONF_TELECOM_DEVICE_ID)
            or entry.data.get(CONF_TELECOM_DEVICE_ID)
            or ""
        ).strip()
        self.update_interval_minutes = self._get_update_interval_minutes(entry)
        self.telecom = Telecom() # 实例化 Telecom 类
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.update_interval_minutes),
        )

    @property
    def masked_phonenum(self):
        return f"{self.phonenum[:3]}****{self.phonenum[7:]}"

    def _get_update_interval_minutes(self, entry):
        value = (
            entry.options.get(CONF_UPDATE_INTERVAL_MINUTES)
            or entry.data.get(CONF_UPDATE_INTERVAL_MINUTES)
            or DEFAULT_UPDATE_INTERVAL_MINUTES
        )
        try:
            return max(int(value), MIN_UPDATE_INTERVAL_MINUTES)
        except (TypeError, ValueError):
            return DEFAULT_UPDATE_INTERVAL_MINUTES

    def _response_data(self, payload):
        if not isinstance(payload, dict):
            return {}
        response_data = payload.get("responseData")
        return response_data if isinstance(response_data, dict) else {}

    def _response_inner_data(self, payload):
        data = self._response_data(payload).get("data")
        return data if isinstance(data, dict) else {}

    def _extract_error_msg(self, payload, default):
        if not isinstance(payload, dict):
            return default

        response_data = self._response_data(payload)
        data = self._response_inner_data(payload)
        login_fail = data.get("loginFailResult") or {}
        header_infos = payload.get("headerInfos") or {}

        result_code = response_data.get("resultCode")
        if result_code == "3006":
            return "3006: 设备未信任，请通过上游短信授权获取 DeviceId，并在集成选项中填写"
        if result_code == "3005":
            return "3005: 服务端要求验证码/二次校验"

        result_desc = (
            login_fail.get("reason")
            or response_data.get("resultDesc")
            or response_data.get("resultMsg")
            or response_data.get("msg")
            or payload.get("error")
            or header_infos.get("reason")
            or header_infos.get("resultDesc")
            or header_infos.get("msg")
        )
        if result_code and result_desc:
            return f"{result_code}: {result_desc}"
        return result_desc or result_code or default

    def _log_payload(self, message, payload):
        _LOGGER.error(
            "%s for %s: %s",
            message,
            self.masked_phonenum,
            self.telecom.format_for_log(payload),
        )

    async def _process_important_data(self, important_data_raw):
        important_data = self._response_inner_data(important_data_raw)
        summary_data = await self.hass.async_add_executor_job(
            self.telecom.to_summary, important_data, self.phonenum
        ) 
        
        # CTM 的 to_summary 返回的数据单位是“分”和“KB”，需要转换为“元”和“GB”
        processed_data = {
            "balance": round(summary_data.get("balance", 0) / 100, 2), # 分转元
            "currentMonthCost": round(summary_data.get("currentMonthCost", 0) / 100, 2), # 新增：分转元
            "voiceUsage": summary_data.get("voiceUsage", 0),
            "voiceBalance": summary_data.get("voiceBalance", 0),
            "voiceTotal": summary_data.get("voiceTotal", 0),
            "flowUse": round(self.telecom.convert_flow(summary_data.get("flowUse", 0), 'GB', 2), 2), # KB 转 GB
            "flowTotal": round(self.telecom.convert_flow(summary_data.get("flowTotal", 0), 'GB', 2), 2), # KB 转 GB
            "flowBalance": round(self.telecom.convert_flow(summary_data.get("flowTotal", 0) - summary_data.get("flowUse", 0), 'GB', 2), 2), # 计算剩余流量
            "flowOver": round(self.telecom.convert_flow(summary_data.get("flowOver", 0), 'GB', 2), 2), # KB 转 GB
            "commonUse": round(self.telecom.convert_flow(summary_data.get("commonUse", 0), 'GB', 2), 2), # KB 转 GB
            "commonTotal": round(self.telecom.convert_flow(summary_data.get("commonTotal", 0), 'GB', 2), 2), # KB 转 GB
            "commonOver": round(self.telecom.convert_flow(summary_data.get("commonOver", 0), 'GB', 2), 2), # KB 转 GB
            "specialUse": round(self.telecom.convert_flow(summary_data.get("specialUse", 0), 'GB', 2), 2), # KB 转 GB
            "specialTotal": round(self.telecom.convert_flow(summary_data.get("specialTotal", 0), 'GB', 2), 2), # KB 转 GB
            "points": summary_data.get("points", 0) # 从 summary_data 获取积分，而不是硬编码为0
        }
        
        # 计算流量使用率
        if processed_data["flowTotal"] > 0:
            processed_data["percentUsed"] = round((processed_data["flowUse"] / processed_data["flowTotal"]) * 100, 2)
        else:
            processed_data["percentUsed"] = 0

        # 计算通话使用率
        if processed_data["voiceTotal"] > 0:
            processed_data["voicePercentUsed"] = round((processed_data["voiceUsage"] / processed_data["voiceTotal"]) * 100, 1)
        else:
            processed_data["voicePercentUsed"] = 0
        
        _LOGGER.debug(f"Processed data before returning: {processed_data}")
        return processed_data

    async def _try_cached_login_info(self):
        cached_login_info = self.entry.data.get(CONF_LOGIN_INFO)
        if not isinstance(cached_login_info, dict):
            return None

        cached_login_info = {**cached_login_info}
        cached_login_info["phonenum"] = self.phonenum
        cached_login_info["password"] = self.password
        self.telecom.set_login_info(cached_login_info)
        _LOGGER.debug("Trying cached China Telecom token for %s.", self.masked_phonenum)

        important_data_raw = await self.hass.async_add_executor_job(
            self.telecom.qry_important_data
        )
        if self._response_inner_data(important_data_raw):
            _LOGGER.debug("Successfully fetched China Telecom data with cached token for %s.", self.masked_phonenum)
            return await self._process_important_data(important_data_raw)

        error_msg = self._extract_error_msg(important_data_raw, "缓存 token 不可用")
        _LOGGER.warning("Cached China Telecom token failed for %s: %s", self.masked_phonenum, error_msg)
        _LOGGER.debug("Cached token failure response for %s: %s", self.masked_phonenum, self.telecom.format_for_log(important_data_raw))
        return None

    def _store_login_info(self, login_info):
        cacheable_login_info = {
            key: value
            for key, value in login_info.items()
            if key not in {"password", "phonenum"}
        }
        new_data = {**self.entry.data, CONF_LOGIN_INFO: cacheable_login_info}
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def _async_update_data(self):
        """Update data via Home Assistant's event loop."""
        login_result = None
        important_data_raw = None
        relogin_result = None
        try:
            cached_data = await self._try_cached_login_info()
            if cached_data is not None:
                return cached_data

            login_result = await self.hass.async_add_executor_job(
                self.telecom.do_login,
                self.phonenum,
                self.password,
                self.telecom_device_id,
            ) 

            login_response_data = self._response_data(login_result)
            if login_response_data.get("resultCode") == "0000":
                login_info = self._response_inner_data(login_result).get("loginSuccessResult")
                if not isinstance(login_info, dict):
                    self._log_payload("China Telecom login response", login_result)
                    raise UpdateFailed("Login failed: 登录成功响应缺少 loginSuccessResult")
                login_info["phonenum"] = self.phonenum
                login_info["password"] = self.password
                self.telecom.set_login_info(login_info) 
                self._store_login_info(login_info)
                _LOGGER.debug(f"Successfully logged in for {self.masked_phonenum}.")
            else:
                error_msg = self._extract_error_msg(login_result, "未知登录失败")
                _LOGGER.error(f"Login failed for {self.masked_phonenum}: {error_msg}")
                self._log_payload("China Telecom login response", login_result)
                raise UpdateFailed(f"Login failed: {error_msg}")

            # 获取重要数据
            important_data_raw = await self.hass.async_add_executor_job(
                self.telecom.qry_important_data
            ) 

            if self._response_inner_data(important_data_raw):
                _LOGGER.debug(f"Successfully fetched important data for {self.masked_phonenum}.")
                return await self._process_important_data(important_data_raw)

            elif isinstance(important_data_raw, dict) and (important_data_raw.get("headerInfos") or {}).get("code") == "X201":
                _LOGGER.warning(f"Token expired for {self.masked_phonenum}. Attempting re-login and retry.")
                relogin_result = await self.hass.async_add_executor_job(
                    self.telecom.do_login,
                    self.phonenum,
                    self.password,
                    self.telecom_device_id,
                ) 
                relogin_response_data = self._response_data(relogin_result)
                if relogin_response_data.get("resultCode") == "0000":
                    relogin_info = self._response_inner_data(relogin_result).get("loginSuccessResult")
                    if not isinstance(relogin_info, dict):
                        self._log_payload("China Telecom re-login response", relogin_result)
                        raise UpdateFailed("Re-login failed: 登录成功响应缺少 loginSuccessResult")
                    relogin_info["phonenum"] = self.phonenum
                    relogin_info["password"] = self.password
                    self.telecom.set_login_info(relogin_info) 
                    self._store_login_info(relogin_info)
                    _LOGGER.debug(f"Successfully re-logged in for {self.masked_phonenum}.")
                    important_data_raw = await self.hass.async_add_executor_job(
                        self.telecom.qry_important_data
                    ) 
                    if self._response_inner_data(important_data_raw):
                        return await self._process_important_data(important_data_raw)
                    else:
                        error_msg = self._extract_error_msg(important_data_raw, "未知数据获取失败")
                        _LOGGER.error(f"Failed to fetch data after re-login: {error_msg}")
                        self._log_payload("China Telecom qryImportantData response after re-login", important_data_raw)
                        raise UpdateFailed(f"Failed to fetch data after re-login: {error_msg}")
                else:
                    relogin_error_msg = self._extract_error_msg(relogin_result, "未知重新登录失败")
                    _LOGGER.error(f"Re-login failed for {self.masked_phonenum}: {relogin_error_msg}")
                    self._log_payload("China Telecom re-login response", relogin_result)
                    raise UpdateFailed(f"Re-login failed: {relogin_error_msg}")
            else:
                error_msg = self._extract_error_msg(important_data_raw, "未知数据获取失败")
                _LOGGER.error(f"Failed to fetch data for {self.masked_phonenum}: {error_msg}")
                self._log_payload("China Telecom qryImportantData response", important_data_raw)
                raise UpdateFailed(f"Failed to fetch data: {error_msg}")

        except UpdateFailed:
            raise
        except Exception as error:
            if login_result is not None:
                self._log_payload("China Telecom last login response before exception", login_result)
            if relogin_result is not None:
                self._log_payload("China Telecom last re-login response before exception", relogin_result)
            if important_data_raw is not None:
                self._log_payload("China Telecom last qryImportantData response before exception", important_data_raw)
            _LOGGER.error(f"Error fetching China Telecom data: {error}", exc_info=True) # 打印详细错误信息
            raise UpdateFailed(f"Error fetching China Telecom data: {error}")


class ChinaTelecomSensor(Entity):
    """Representation of a China Telecom sensor."""

    def __init__(self, coordinator, key, name, unit, icon, device_id):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.key = key
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_id = device_id
        phonenum_full = self.coordinator.phonenum
        self.masked_phonenum = f"{phonenum_full[:3]}****{phonenum_full[7:]}"
        self._unique_id = f"{self.masked_phonenum}_{device_id}_{key}"  # 在实体 ID 中添加号码

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        # 确保数据存在且键存在，否则返回 None
        if self.coordinator.data and self.key in self.coordinator.data:
            return self.coordinator.data.get(self.key)
        return None # 或其他默认值，例如 0

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"{self.masked_phonenum} 套餐信息",
            "manufacturer": "中国电信",
            "entry_type": DeviceEntryType.SERVICE,
            "model": "CTM中国电信", 
            "sw_version": "1.1.6" 
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity. Only used by the generic entity update service."""
        await self.coordinator.async_request_refresh()
