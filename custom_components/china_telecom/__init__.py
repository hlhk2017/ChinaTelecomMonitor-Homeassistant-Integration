import logging
import asyncio
import os
from contextlib import suppress

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CARD_RESOURCE_URL = "/china_telecom/ctm-telecom-card.js"
LEGACY_CARD_RESOURCE_URL = "/local/ctm-telecom-card.js"
CARD_RESOURCE_PREFIXES = (CARD_RESOURCE_URL, LEGACY_CARD_RESOURCE_URL)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the China Telecom component from configuration.yaml."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=entry_config,
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up China Telecom integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await async_register_lovelace_resource(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload China Telecom when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the CTM Telecom card as a Lovelace resource."""
    if hass.data.setdefault(DOMAIN, {}).get("card_resource_registered"):
        return

    await async_setup_component(hass, "lovelace", {})
    await async_register_card_static_path(hass)

    version = await hass.async_add_executor_job(_card_resource_version, hass)
    resource_url = f"{CARD_RESOURCE_URL}?v={version}"

    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.warning("Can not access Lovelace data, injecting card resource only")
        add_extra_js_url(hass, resource_url)
        hass.data[DOMAIN]["card_resource_registered"] = True
        return

    resources = lovelace.resources if hasattr(lovelace, "resources") else lovelace.get("resources")
    if resources is None:
        _LOGGER.warning("Can not access Lovelace resources, injecting card resource only")
        add_extra_js_url(hass, resource_url)
        hass.data[DOMAIN]["card_resource_registered"] = True
        return

    with suppress(Exception):
        if hasattr(resources, "async_get_info"):
            await resources.async_get_info()
        elif not resources.loaded:
            await resources.async_load()

    for item in resources.async_items():
        if not item.get("url", "").startswith(CARD_RESOURCE_PREFIXES):
            continue

        if item["url"] != resource_url and isinstance(resources, ResourceStorageCollection):
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": resource_url}
            )
            _LOGGER.info("Updated CTM Telecom card resource: %s", resource_url)
        hass.data[DOMAIN]["card_resource_registered"] = True
        return

    if isinstance(resources, ResourceStorageCollection):
        await resources.async_create_item({"res_type": "module", "url": resource_url})
        _LOGGER.info("Registered CTM Telecom card resource: %s", resource_url)
    else:
        add_extra_js_url(hass, resource_url)
        _LOGGER.info("Injected CTM Telecom card resource: %s", resource_url)

    hass.data[DOMAIN]["card_resource_registered"] = True


async def async_register_card_static_path(hass: HomeAssistant) -> None:
    """Expose the bundled frontend card from the integration directory."""
    if hass.data.setdefault(DOMAIN, {}).get("card_static_path_registered"):
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_RESOURCE_URL,
                hass.config.path("custom_components", DOMAIN, "www", "ctm-telecom-card.js"),
                True,
            )
        ]
    )
    hass.data[DOMAIN]["card_static_path_registered"] = True


def _card_resource_version(hass: HomeAssistant) -> str:
    """Return a cache-busting version for the frontend card."""
    card_path = hass.config.path("custom_components", DOMAIN, "www", "ctm-telecom-card.js")
    with suppress(OSError):
        return str(int(os.path.getmtime(card_path)))
    return "1"
