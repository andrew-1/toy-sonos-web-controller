
import views

def test_get_sonos_controller():
    app = {
        'controller_paths': {
            "livingroom": "Living Room",
            "bedroom": "Bedroom",
        },
        'controllers': {
            "Living Room": "a_controller",
            "Bedroom": "b_controller",
        }
    }
    assert views._get_sonos_controller(app, "livingroom") == "a_controller"
    assert views._get_sonos_controller(app, "abc") == "a_controller"
    assert views._get_sonos_controller(app, "LivingRoom") == "a_controller"
    assert views._get_sonos_controller(app, "Bedroom") == "b_controller"
    assert views._get_sonos_controller(app, "B e d r o o m") == "a_controller"
