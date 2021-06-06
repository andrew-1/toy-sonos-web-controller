"""Code to process UnPn dicts that are provided by soco as events
and triger callbacks to the controller class
"""

from __future__ import annotations
from collections import defaultdict
from typing import Callable

import soco
from soco import events_asyncio


soco.config.EVENTS_MODULE = events_asyncio


class SocoEventHandler:
    def __init__(
        self, 
        subscription: events_asyncio.Subscription,
        callback_sonos_event: Callable[[bool, str, int], None],
        playback_controller_queues_empty: Callable[[], bool],
    ) -> None:

        self.subscription = subscription
        self.subscription.callback = self._callback
        self._events: list = 3 * [defaultdict(str)]
        self._callback_sonos_event = callback_sonos_event
        self._playback_controller_queues_empty = \
            playback_controller_queues_empty

    def _callback(self, event):
        if not self._playback_controller_queues_empty():
            # if there are unprocessed commands don't send the update
            return

        queue_update_required = self._queue_changed(event.variables)
        current_state = event.variables['transport_state']
        current_track = int(event.variables['current_track']) - 1
        self._callback_sonos_event(
            queue_update_required,
            current_state,
            current_track
        )

    def _queue_changed(self, event_variables):
        """Attempts to work out whether queue has changed"""
        # do this on strings, as hashable objects seem to be being created
        # on each call
        
        values = ('number_of_tracks', 'transport_state')
        if not all(val in event_variables for val in values):
            # if the event doesn't have the above, ignore it
            return

        variables = {
            k: v 
            for k, v in event_variables.items() 
            if isinstance(v, str)
        }
        events = self._events
        events[:] = events[-2], events[-1], variables
        
        different_number_of_tracks = (
            events[-2]['number_of_tracks'] != events[-1]['number_of_tracks']
        )
        is_stopped = events[-1]['transport_state'] == "STOPPED"

        is_not_transitioning = (
            events[-1]['transport_state'] != "TRANSITIONING"
        )
        no_change_in_variables = (
            not set(events[-1].items()) - set(events[-2].items())
        )
        two_back_state_not_transitioning = (
            events[-3]['transport_state'] != "TRANSITIONING"
        )
        not_two_identical_events_after_a_transition = (
            is_not_transitioning 
            and no_change_in_variables
            and two_back_state_not_transitioning
        )
        update_required = (
            different_number_of_tracks
            or is_stopped
            or not_two_identical_events_after_a_transition
        )
        return update_required

    async def clean_up(self) -> None:
        await self.subscription.unsubscribe()

    @staticmethod
    async def shutdown_event_listener():
        await events_asyncio.event_listener.async_stop()