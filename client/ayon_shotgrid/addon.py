import os
import ayon_api

from openpype.modules import (
    OpenPypeModule,
    ITrayModule,
    IPluginPaths,
)

SHOTGRID_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(OpenPypeModule, ITrayModule, IPluginPaths):
    name = "shotgrid"
    enabled = True
    tray_wrapper = None

    def initialize(self, modules_settings):
        module_settings = modules_settings.get(self.name, dict())
        self._shotgrid_server_url = module_settings.get("shotgrid_server")
        self._shotgrid_script_name = module_settings.get("shotgrid_api_secret")
        self._shotgrid_api_key = None

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def create_shotgrid_session(self):
        from .lib import credentials

        sg_username, sg_password = credentials.get_local_login()

        secret = self.get_shotgrid_secret_data()
        login_args = {'base_url': self._shotgrid_server_url}
        if secret:
            login_args['script_name'] = secret.get('name')
            login_args['api_key'] = secret.get('value')
            login_args['sudo_as_login'] = sg_username
        else:
            login_args['login'] = sg_username
            login_args['password'] = sg_password

        if not any(login_args.values()):
            return None

        return credentials.create_sg_session(**login_args)

    def tray_init(self):
        from .tray.shotgrid_tray import ShotgridTrayWrapper
        self.tray_wrapper = ShotgridTrayWrapper(self)

    def tray_start(self):
        return self.tray_wrapper.set_username_label()

    def tray_exit(self, *args, **kwargs):
        return self.tray_wrapper

    def tray_menu(self, tray_menu):
        return self.tray_wrapper.tray_menu(tray_menu)

    def get_shotgrid_secret_data(self):
        """Gets shotgrid data from server for login.

        Returns:
            (dict): script_name under 'name' key and api_key under 'value' key.

        """
        ayon_server_api = ayon_api.get_server_api_connection()

        secret = ''
        try:
            secret = ayon_server_api.get_secret(self._shotgrid_script_name)
            return secret
        except ayon_api.exceptions.HTTPRequestError:
            return secret
