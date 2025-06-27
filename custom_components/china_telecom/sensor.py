import logging
import asyncio

from datetime import timedelta
import uuid
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import DOMAIN, CONF_PHONENUM, CONF_PASSWORD, CONF_DEVICE_ID #

# 导入 telecom_class
from .telecom_class import Telecom #

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
        hass, phonenum, password 
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
    async_add_entities(sensors)


class ChinaTelecomDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching China Telecom data."""

    def __init__(self, hass, phonenum, password): 
        """Initialize."""
        self.phonenum = phonenum
        self.password = password
        self.telecom = Telecom() # 实例化 Telecom 类
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=6),
        )

    async def _async_update_data(self):
        """Update data via Home Assistant's event loop."""
        try:
            # 登录逻辑
            # 由于 telecom_class.py 中的 do_login 和 qry_important_data 是同步的，
            # 需要在 Home Assistant 的事件循环中以异步方式运行它们。
            login_result = await self.hass.async_add_executor_job(
                self.telecom.do_login, self.phonenum, self.password
            ) #

            if login_result.get("responseData", {}).get("resultCode") == "0000":
                login_info = login_result["responseData"]["data"]["loginSuccessResult"]
                login_info["phonenum"] = self.phonenum
                login_info["password"] = self.password # 存储密码以便后续查询使用
                self.telecom.set_login_info(login_info) #
                _LOGGER.debug(f"Successfully logged in for {self.phonenum}.")
            else:
                error_msg = login_result.get("responseData", {}).get("data", {}).get("loginFailResult", {}).get("reason", "未知登录失败")
                _LOGGER.error(f"Login failed for {self.phonenum}: {error_msg}")
                raise UpdateFailed(f"Login failed: {error_msg}")

            # 获取重要数据
            important_data_raw = await self.hass.async_add_executor_job(
                self.telecom.qry_important_data
            ) #

            if important_data_raw.get("responseData"):
                _LOGGER.debug(f"Successfully fetched important data for {self.phonenum}.")
                summary_data = await self.hass.async_add_executor_job(
                    self.telecom.to_summary, important_data_raw["responseData"]["data"], self.phonenum
                ) #
                
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
                    "points": 0 # CTM 的 to_summary 没有直接提供积分，这里暂设为0
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

                return processed_data

            elif important_data_raw.get("headerInfos", {}).get("code") == "X201":
                _LOGGER.warning(f"Token expired for {self.phonenum}. Attempting re-login and retry.")
                # Token 过期，再次尝试登录并重新获取数据
                relogin_result = await self.hass.async_add_executor_job(
                    self.telecom.do_login, self.phonenum, self.password
                ) #
                if relogin_result.get("responseData", {}).get("resultCode") == "0000":
                    relogin_info = relogin_result["responseData"]["data"]["loginSuccessResult"]
                    relogin_info["phonenum"] = self.phonenum
                    relogin_info["password"] = self.password
                    self.telecom.set_login_info(relogin_info) #
                    _LOGGER.debug(f"Successfully re-logged in for {self.phonenum}.")
                    important_data_raw = await self.hass.async_add_executor_job(
                        self.telecom.qry_important_data
                    ) #
                    if important_data_raw.get("responseData"):
                        summary_data = await self.hass.async_add_executor_job(
                            self.telecom.to_summary, important_data_raw["responseData"]["data"], self.phonenum
                        ) #
                        processed_data = {
                            "balance": round(summary_data.get("balance", 0) / 100, 2), # 分转元
                            "currentMonthCost": round(summary_data.get("currentMonthCost", 0) / 100, 2), # 新增：分转元
                            "voiceUsage": summary_data.get("voiceUsage", 0),
                            "voiceBalance": summary_data.get("voiceBalance", 0),
                            "voiceTotal": summary_data.get("voiceTotal", 0),
                            "flowUse": round(self.telecom.convert_flow(summary_data.get("flowUse", 0), 'GB', 2), 2),
                            "flowTotal": round(self.telecom.convert_flow(summary_data.get("flowTotal", 0), 'GB', 2), 2),
                            "flowBalance": round(self.telecom.convert_flow(summary_data.get("flowTotal", 0) - summary_data.get("flowUse", 0), 'GB', 2), 2),
                            "flowOver": round(self.telecom.convert_flow(summary_data.get("flowOver", 0), 'GB', 2), 2),
                            "commonUse": round(self.telecom.convert_flow(summary_data.get("commonUse", 0), 'GB', 2), 2),
                            "commonTotal": round(self.telecom.convert_flow(summary_data.get("commonTotal", 0), 'GB', 2), 2),
                            "commonOver": round(self.telecom.convert_flow(summary_data.get("commonOver", 0), 'GB', 2), 2),
                            "specialUse": round(self.telecom.convert_flow(summary_data.get("specialUse", 0), 'GB', 2), 2),
                            "specialTotal": round(self.telecom.convert_flow(summary_data.get("specialTotal", 0), 'GB', 2), 2),
                            "points": 0
                        }
                        if processed_data["flowTotal"] > 0:
                            processed_data["percentUsed"] = round((processed_data["flowUse"] / processed_data["flowTotal"]) * 100, 2)
                        else:
                            processed_data["percentUsed"] = 0

                        if processed_data["voiceTotal"] > 0:
                            processed_data["voicePercentUsed"] = round((processed_data["voiceUsage"] / processed_data["voiceTotal"]) * 100, 1)
                        else:
                            processed_data["voicePercentUsed"] = 0
                        return processed_data
                    else:
                        error_msg = important_data_raw.get("headerInfos", {}).get("reason", "未知数据获取失败")
                        _LOGGER.error(f"Failed to fetch data after re-login: {error_msg}")
                        raise UpdateFailed(f"Failed to fetch data after re-login: {error_msg}")
                else:
                    relogin_error_msg = relogin_result.get("responseData", {}).get("data", {}).get("loginFailResult", {}).get("reason", "未知重新登录失败")
                    _LOGGER.error(f"Re-login failed for {self.phonenum}: {relogin_error_msg}")
                    raise UpdateFailed(f"Re-login failed: {relogin_error_msg}")
            else:
                error_msg = important_data_raw.get("headerInfos", {}).get("reason", "未知数据获取失败")
                _LOGGER.error(f"Failed to fetch data for {self.phonenum}: {error_msg}")
                raise UpdateFailed(f"Failed to fetch data: {error_msg}")

        except Exception as error:
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
            "model": "CTM中国电信", # 
            "sw_version": "1.0.7" 
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
