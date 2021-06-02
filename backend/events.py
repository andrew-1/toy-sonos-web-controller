"""Code to process UnPn dicts that are provided by soco as events
and triger callbacks to the controller class
"""

from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

import soco
from soco import events_asyncio


if TYPE_CHECKING:
    from soco.events_asyncio import Subscription

soco.config.EVENTS_MODULE = events_asyncio


class SonosEventHandler:
    def __init__(self, subscription: Subscription):
        self.subscription = subscription
        self.subscription.callback = self._callback
        self._events: list[dict] = [
            {}, defaultdict(str), defaultdict(str)
        ]
        self.controller_callback = None

    def _callback(self, event):

        queue_update_required = self._queue_changed(event.variables)
        current_state = event.variables['transport_state']
        current_track = int(event.variables['current_track']) - 1
        
        self.controller_callback(
            queue_update_required,
            current_state,
            current_track
        )

    def _queue_changed(self, event_variables):
        """Attempts to work out whether queue has changed"""
        # do this on strings, as hashable objects seem to be being created
        # on each call
        variables = {
            k: v 
            for k, v in event_variables.items() 
            if isinstance(v, str)
        }
        events = self._events
        events[:] = events[-2:], events[-1], variables
        
        different_number_of_tracks = lambda: (
            events[-2]['number_of_tracks'] != events[-1]['number_of_tracks']
        )
        is_stopped = lambda: (
            events[-1]['transport_state'] == "STOPPED"
        )
        is_not_transitioning = lambda: (
            events[-1]['transport_state'] != "TRANSITIONING"
        )
        no_change_in_variables = lambda: (
            not set(events[-1].items()) - set(events[-2].items())
        )
        two_back_state_not_transitioning = lambda: (
            events[-3]['transport_state'] != "TRANSITIONING"
        )
        not_two_identical_events_after_a_transition = lambda: (
            is_not_transitioning() 
            and no_change_in_variables()
            and two_back_state_not_transitioning()
        )

        return (
            different_number_of_tracks()
            or is_stopped()
            or not_two_identical_events_after_a_transition()
        )
