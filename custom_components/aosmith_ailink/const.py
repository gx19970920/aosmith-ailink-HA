"""Constants for the A. O. Smith AILink integration."""

from __future__ import annotations

DOMAIN = "aosmith_ailink"

DEFAULT_BASE_URL = "https://ailink-api.hotwater.com.cn"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TIMEOUT = 20

CONF_ACCESS_TOKEN = "access_token"
CONF_BASE_URL = "base_url"
CONF_DEVICE_ID = "device_id"
CONF_FAMILY_ID = "family_id"
CONF_MOBILE = "mobile"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_USER_ID = "user_id"
CONF_VERIFY_SSL = "verify_ssl"

API_PREFIX = "/AiLinkService"

ENDPOINT_LOGIN = f"{API_PREFIX}/user/login"
ENDPOINT_FAMILY_LIST = f"{API_PREFIX}/family/getFamilyList"
ENDPOINT_FAMILY_INDEX = f"{API_PREFIX}/user/getFamilyIndex"
ENDPOINT_DEVICE_CURR_INFO = f"{API_PREFIX}/appDevice/getDeviceCurrInfo"
ENDPOINT_DEVICE_LIST = f"{API_PREFIX}/device/getDeviceList"
ENDPOINT_HOMEPAGE_V2 = f"{API_PREFIX}/appDevice/getHomepageV2"
ENDPOINT_USER_DEVICE_LIST = f"{API_PREFIX}/device/getUserDeviceList"
ENDPOINT_INVOKE = f"{API_PREFIX}/device/invokeMethod"
ENDPOINT_REALTIME = f"{API_PREFIX}/tsDevice/startRealTimeData"

PLATFORMS = ["sensor", "climate", "switch"]

SERVICE_INVOKE_METHOD = "invoke_method"
SERVICE_SET_HEATING = "set_heating"
SERVICE_START_ONE_KEY_QUICK_WASH = "start_one_key_quick_wash"
SERVICE_START_24H_QUICK_WASH = "start_24h_quick_wash"
