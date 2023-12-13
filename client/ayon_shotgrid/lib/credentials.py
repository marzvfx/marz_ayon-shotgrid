import shotgun_api3
from shotgun_api3.shotgun import AuthenticationFault

from openpype.lib import OpenPypeSettingsRegistry


def check_user_permissions(**kwargs):
    """Check if the provided user can access the Shotgrid API.

    Args:
        base_url (str): The Shotgun server URL.
        login (str): The Shotgrid login username.
        password (str): The Shotgrid login password.
        script_name (str): Name of the Shotgrid script name used for login.
        api_key (str): key related to shotgrid script name.
        sudo_as_login (str): The Shotgrid login username.
        
    Returns:
        tuple(bool, str): Whether the connection was succsefull or not, and a 
            string message with the result.
     """
    if not any(kwargs.values()):
        print('check_user_permissions: ', kwargs)
        return (False, "Missing a field.")

    try:
        session = create_sg_session(**kwargs)
        session.close()
    except AuthenticationFault as e:
        return (False, str(e))

    return (True, "Succesfully logged in.")


def clear_local_login():
    """Clear the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    reg.delete_item("shotgrid_login")


def create_sg_session(**kwargs):
    """Attempt to create a Shotgun Session

    Args:
        base_url (str): The Shotgun server URL.
        login (str): The Shotgrid login username.
        password (str): The Shotgrid login password.
        script_name (str): Name of the Shotgrid script name used for login.
        api_key (str): key related to shotgrid script name.
        sudo_as_login (str): The Shotgrid login username.

    Returns:
        session (shotgun_api3.Shotgun): A Shotgrid API Session.

    Raises:
        AuthenticationFault: If the authentication with Shotgrid fails.
    """

    session = shotgun_api3.Shotgun(**kwargs)

    session.preferences_read()

    return session


def get_local_login():
    """Get the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    try:
        return reg.get_item("shotgrid_login")
    except Exception:
        return (None, None)


def save_local_login(username, password):
    """Save the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    reg.set_item("shotgrid_login", (username, password))

