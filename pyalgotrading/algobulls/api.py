"""
Module for handling API calls to the [AlgoBulls](https://www.algobulls.com) backend.
"""
import re
from json import JSONDecodeError
from datetime import datetime as dt, timezone

import requests

from .exceptions import AlgoBullsAPIBaseException, AlgoBullsAPIUnauthorizedError, AlgoBullsAPIInsufficientBalanceError, AlgoBullsAPIResourceNotFoundError, AlgoBullsAPIBadRequest, AlgoBullsAPIInternalServerErrorException, AlgoBullsAPIForbiddenError
from ..constants import TradingType, TradingReportType, MESSAGE_REALTRADING_FORBIDDEN


class AlgoBullsAPI:
    """
    AlgoBulls API
    """
    SERVER_ENDPOINT = 'https://api.algobulls.com/'

    # SERVER_ENDPOINT = 'http://127.0.0.1:8000/'

    def __init__(self):
        """
        Init method that is used while creating an object of this class
        """
        self.headers = None
        self.__key_backtesting = {}  # strategy-cstc_id mapping
        self.__key_papertrading = {}  # strategy-cstc_id mapping
        self.__key_realtrading = {}  # strategy-cstc_id mapping
        self.pattern = re.compile(r'(?<!^)(?=[A-Z])')

    def __convert(self, _dict):
        # Helps convert _dict keys from camelcase to snakecase
        return {self.pattern.sub('_', k).lower(): v for k, v in _dict.items()}

    def set_access_token(self, access_token: str):
        """
        Set access token to the header attribute, which is needed for APIs requiring authorization
        Package for interacting with AlgoBulls Algorithmic Trading Platform (https://www.algobulls.com)

        Args:
            access_token: Access token generated by logging to the URL given by the `get_authorization_url()` method
        """
        self.headers = {
            'Authorization': f'{access_token}'
        }

    def _send_request(self, method: str = 'get', endpoint: str = '', base_url: str = SERVER_ENDPOINT, params: [str, dict] = None, json_data: [str, dict] = None, requires_authorization: bool = True) -> dict:
        """
        Send the request to the platform
        
        Args:
            method: get
            endpoint: endpoint url
            base_url: base url
            params: parameters
            json_data: json data as body
            requires_authorization: True or False

        Returns:
            request status
        """
        url = f'{base_url}{endpoint}'
        headers = self.headers if requires_authorization else None
        response = requests.request(method=method, headers=headers, url=url, params=params, json=json_data)

        try:
            response_json = response.json()
        except JSONDecodeError:
            response_json = str(response)

        if response.status_code == 200:
            response_json = response.json()
            return response_json
        elif response.status_code == 400:
            raise AlgoBullsAPIBadRequest(method=method, url=url, response=response_json)
        elif response.status_code == 401:
            raise AlgoBullsAPIUnauthorizedError(method=method, url=url, response=response_json)
            # try:
            #     raise AlgoBullsAPIUnauthorizedError(method=method, url=url, response=response_json)
            # except AlgoBullsAPIUnauthorizedError as ex:
            #     print(f'{ex.get_error_type()}. {ex.response}')
        elif response.status_code == 402:
            raise AlgoBullsAPIInsufficientBalanceError(method=method, url=url, response=response_json)
        elif response.status_code == 403:
            raise AlgoBullsAPIForbiddenError(method=method, url=url, response=response_json)
        elif response.status_code == 404:
            raise AlgoBullsAPIResourceNotFoundError(method=method, url=url, response=response_json)
        elif response.status_code == 500:
            raise AlgoBullsAPIInternalServerErrorException(method=method, url=url, response=response_json)
        else:
            response.raw.decode_content = True
            raise AlgoBullsAPIBaseException(method=method, url=url, response=response_json)

    def __fetch_key(self, strategy_code, trading_type):
        """
        Add strategy to Back Testing
        
        Args:
            strategy_code: strategy code
            trading_type: trading type

        Returns:
            key

        Info: ENDPOINT
            `POST` v2/portfolio/strategy
            `PUT` v2/portfolio/strategy
            `PATCH` v2/portfolio/strategy
        """

        endpoint = f'v2/portfolio/strategy'
        json_data = {'strategyId': strategy_code, 'tradingType': trading_type.value}

        # This api fails for some weird reason
        # response = self._send_request(method='options', endpoint=endpoint, json_data=json_data)

        if trading_type is TradingType.REALTRADING:
            response = self._send_request(method='post', endpoint=endpoint, json_data=json_data)
        elif trading_type is TradingType.PAPERTRADING:
            response = self._send_request(method='put', endpoint=endpoint, json_data=json_data)
        elif trading_type is TradingType.BACKTESTING:
            response = self._send_request(method='patch', endpoint=endpoint, json_data=json_data)
        else:
            raise NotImplementedError

        key = response.get('key')
        return key

    def __get_key(self, strategy_code, trading_type):
        if trading_type is TradingType.BACKTESTING:
            if self.__key_backtesting.get(strategy_code) is None:
                self.__key_backtesting[strategy_code] = self.__fetch_key(strategy_code=strategy_code, trading_type=TradingType.BACKTESTING)
            return self.__key_backtesting[strategy_code]
        elif trading_type is TradingType.PAPERTRADING:
            if self.__key_papertrading.get(strategy_code) is None:
                self.__key_papertrading[strategy_code] = self.__fetch_key(strategy_code=strategy_code, trading_type=TradingType.PAPERTRADING)
            return self.__key_papertrading[strategy_code]
        elif trading_type is TradingType.REALTRADING:
            if self.__key_realtrading.get(strategy_code) is None:
                self.__key_realtrading[strategy_code] = self.__fetch_key(strategy_code=strategy_code, trading_type=TradingType.REALTRADING)
            return self.__key_realtrading[strategy_code]
        else:
            raise NotImplementedError

    def create_strategy(self, strategy_name: str, strategy_details: str, abc_version: str) -> dict:
        """
        Create a new strategy for the user on the AlgoBulls platform.

        Args:
            strategy_name: name of the strategy
            strategy_details: Python code of the strategy
            abc_version: value of one of the enums available under [AlgoBullsEngineVersion]()

        Returns:
            JSON Response received from AlgoBulls platform after (attempt to) creating a new strategy.

        Warning:
            For every user, the `strategy_name` should be unique. You cannot create multiple strategies with the same name.

        Info: ENDPOINT
            `POST` v2/user/strategy/build/python
        """
        try:
            json_data = {'strategyName': strategy_name, 'strategyDetails': strategy_details, 'abcVersion': abc_version}
            endpoint = f'v3/build/python/user/strategy/code'
            print(f"Uploading strategy '{strategy_name}' ...", end=' ')
            response = self._send_request(endpoint=endpoint, method='post', json_data=json_data)
            print('Success.')
            return response
        except (AlgoBullsAPIForbiddenError, AlgoBullsAPIInsufficientBalanceError) as ex:
            print('Fail.')
            print(f'{ex.get_error_type()}: {ex.response}')

    def update_strategy(self, strategy_code: str, strategy_name: str, strategy_details: str, abc_version: str) -> dict:
        """
        Update an already existing strategy on the AlgoBulls platform

        Args:
            strategy_code: unique code of the strategy
            strategy_name: name of the strategy
            strategy_details: Python code of the strategy
            abc_version: value of one of the enums available under `AlgoBullsEngineVersion`

        Returns:
            JSON Response received from AlgoBulls platform after (attempt to) updating an existing strategy.

        Info: ENDPOINT
            PUT v2/user/strategy/build/python
        """
        json_data = {'strategyId': strategy_code, 'strategyName': strategy_name, 'strategyDetails': strategy_details, 'abcVersion': abc_version}
        endpoint = f'v3/build/python/user/strategy/code'
        response = self._send_request(endpoint=endpoint, method='put', json_data=json_data)
        return response

    def get_all_strategies(self) -> dict:
        """
        Get all the Python strategies created by the user on the AlgoBulls platform

        Returns:
            JSON Response received from AlgoBulls platform with list of all the created strategies.

        Info: ENDPOINT
            `OPTIONS` v3/build/python/user/strategy/code
        """
        endpoint = f'v3/build/python/user/strategy/code'
        response = self._send_request(endpoint=endpoint, method='options')
        return response

    def get_strategy_details(self, strategy_code: str) -> dict:
        """
        Get strategy details for a particular strategy

        Args:
            strategy_code: unique code of strategy, which is received while creating the strategy or

        Returns:
            JSON
            
        Info: ENDPOINT
            `GET` v3/build/python/user/strategy/code/{strategy_code}
        """
        params = {}
        endpoint = f'v3/build/python/user/strategy/code/{strategy_code}'
        response = self._send_request(endpoint=endpoint, params=params)
        return response

    def search_instrument(self, tradingsymbol: str, exchange: str) -> dict:
        """
        Search for an instrument using its trading symbol
        
        Args:
            tradingsymbol: instrument tradingsymbol
            exchange: instrument exchange

        Returns:
            JSON Response
            
        INFO: ENDPOINT
            `GET` v4/portfolio/searchInstrument
        """
        params = {'search': tradingsymbol, 'exchange': exchange}
        endpoint = f'v4/portfolio/searchInstrument'
        response = self._send_request(endpoint=endpoint, params=params, requires_authorization=False)
        return response

    def set_strategy_config(self, strategy_code: str, strategy_config: dict, trading_type: TradingType) -> (str, dict):
        """
        Set configuration before running a strategy
        
        Args:
            strategy_code: strategy code
            strategy_config: strategy configuration
            trading_type: BACKTESTING, PAPER TRADING or REAL TRADING

        Returns:

        Info: ENDPOINT
           `POST` v4/portfolio/tweak/{key}/?isPythonBuild=true
        """

        # Configure the params
        key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
        endpoint = f'v4/portfolio/tweak/{key}?isPythonBuild=true'
        print('Setting Strategy Config...', end=' ')
        response = self._send_request(method='post', endpoint=endpoint, json_data=strategy_config)
        print('Success.')
        return key, response

    def start_strategy_algotrading(self, strategy_code: str, start_timestamp: dt, end_timestamp: dt, trading_type: TradingType, lots: int) -> dict:
        """
        Submit Backtesting / Paper Trading / Real Trading job for strategy with code strategy_code & return the job ID.
        
        Args:
            strategy_code: Strategy code
            start_timestamp: Start date/time
            end_timestamp: End date/time
            trading_type: Trading type
            lots: Lots

        Info: ENDPOINT
            `PATCH` v4/portfolio/strategies?isPythonBuild=true
        """
        if trading_type == TradingType.REALTRADING:
            return {'message': MESSAGE_REALTRADING_FORBIDDEN}
        elif trading_type in [TradingType.PAPERTRADING, TradingType.BACKTESTING]:
            endpoint = 'v4/portfolio/strategies?isPythonBuild=true'
        else:
            raise NotImplementedError

        try:
            key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
            map_trading_type_to_date_key = {
                TradingType.REALTRADING: 'liveDataTime',
                TradingType.PAPERTRADING: 'backDataTime',
                TradingType.BACKTESTING: 'backDataDate'
            }
            _timestamp_format = "%d-%m-%YT%H:%MZ"
            execute_config = {
                map_trading_type_to_date_key[trading_type]: [start_timestamp.astimezone().astimezone(timezone.utc).isoformat(), end_timestamp.astimezone().astimezone(timezone.utc).isoformat()],
                'isLiveDataTestMode': trading_type == TradingType.PAPERTRADING,
                'customizationsQuantity': lots
            }
            json_data = {'method': 'update', 'newVal': 1, 'key': key, 'record': {'status': 0, 'lots': lots, 'executeConfig': execute_config}, 'dataIndex': 'executeConfig'}
            print(f'Submitting {trading_type.name} job...', end=' ')
            response = self._send_request(method='patch', endpoint=endpoint, json_data=json_data)
            print('Success.')
            return response
        except (AlgoBullsAPIForbiddenError, AlgoBullsAPIInsufficientBalanceError) as ex:
            print('Fail.')
            print(f'{ex.get_error_type()}: {ex.response}')

    def stop_strategy_algotrading(self, strategy_code: str, trading_type: TradingType) -> dict:
        """
        Stop Backtesting / Paper Trading / Real Trading job for strategy with code strategy_code & return the job ID.
        
        Args:
            strategy_code: Strategy code
            trading_type: Trading type
        
        Info: ENDPOINT
            `POST` v4/portfolio/strategies
        """
        if trading_type == TradingType.REALTRADING:
            return {'message': 'Please get approval for your strategy by writing to support@algobulls.com. Once approved, you can STOP the strategy in REALTRADING mode directly from the website.'}
        elif trading_type in [TradingType.PAPERTRADING, TradingType.BACKTESTING]:
            endpoint = 'v4/portfolio/strategies'
        else:
            raise NotImplementedError

        try:
            key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
            json_data = {'method': 'update', 'newVal': 0, 'key': key, 'record': {'status': 2}, 'dataIndex': 'executeConfig'}
            print(f'Stopping {trading_type.name} job...', end=' ')
            response = self._send_request(method='patch', endpoint=endpoint, json_data=json_data)
            print('Success.')
            return response
        except (AlgoBullsAPIForbiddenError, AlgoBullsAPIInsufficientBalanceError) as ex:
            print('Fail.')
            print(f'{ex.get_error_type()}: {ex.response}')

    def get_job_status(self, strategy_code: str, trading_type: TradingType) -> dict:
        """
        Get status for a Back Testing / Paper Trading / Real Trading Job

        Args:
            strategy_code: Strategy code
            trading_type: Trading type

        Returns:
            Job status

        Info: ENDPOINT
            `GET` v2/user/strategy/status
        """
        key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
        params = {'key': key}
        endpoint = f'v2/user/strategy/status'
        response = self._send_request(endpoint=endpoint, params=params)
        return response

    def get_logs(self, strategy_code: str, trading_type: TradingType) -> dict:
        """
        Fetch logs for a strategy
        
        Args:
            strategy_code: Strategy code
            trading_type: Trading type
        
        Returns:
            Execution logs
            
        Info: ENDPOINT
            `POST`: v2/user/strategy/logs
        """
        endpoint = 'v2/user/strategy/logs'
        key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
        json_data = {'key': key}
        response = self._send_request(method='post', endpoint=endpoint, json_data=json_data)
        return response

    def get_reports(self, strategy_code: str, trading_type: TradingType, report_type: TradingReportType) -> dict:
        """
        Fetch report for a strategy

        Args:
            strategy_code: Strategy code
            trading_type: Value of TradingType Enum
            report_type: Value of TradingReportType Enum

        Returns:
            Report data

        Info: ENDPOINT
            `GET` v2/user/strategy/pltable          for P&L Table
            `GET` v2/user/strategy/statstable       for Stats Table
            `GET` v2/user/strategy/orderhistory     Order History
        """
        if report_type is TradingReportType.PNL_TABLE:
            endpoint = 'v2/user/strategy/pltable'
        elif report_type is TradingReportType.STATS_TABLE:
            endpoint = 'v2/user/strategy/statstable'
        elif report_type is TradingReportType.ORDER_HISTORY:
            endpoint = 'v2/user/strategy/orderhistory'
        else:
            raise NotImplementedError

        key = self.__get_key(strategy_code=strategy_code, trading_type=trading_type)
        params = {'key': key}
        response = self._send_request(endpoint=endpoint, params=params)
        return response
