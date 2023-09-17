from gettext import NullTranslations
from operator import truediv
import os
import json
import re
from typing import Dict, Text, Any, List
import logging
from urllib import response
from dateutil import parser
import sqlalchemy as sa
import sqlite3
import json
from numpy import random
import actions.mysql as mysql

import twilio
from twilio.rest import Client

import pymongo

import spacy
import en_core_web_sm
import nltk
from nltk.corpus import wordnet
from bltk.langtools import PosTagger
from bltk.langtools import Tokenizer

import bangla
from banglanum2words import num_convert
from num2words import num2words

import datetime
from datetime import date
import requests

from rasa_sdk.events import ReminderScheduled

#Global variable is here
#-----------------------------------------------------
nlp = en_core_web_sm.load()
nlu = spacy.load("en_core_web_sm")
# UserText = None
GlobalList = []
flag = False
#-----------------------------------------------------

numeric_words = {
      '.': 'দশমিক',
      '০': 'শূন্য',
      '১': 'এক',
      '০১ ': 'এক',
      '2': 'দুই',
      '০২': 'দুই',
      '৩': 'তিন',
      '০৩': 'তিন',
      '৪': 'চার',
      '০৪': 'চার',
      '৫': 'পাঁচ',
      '০৫': 'পাঁচ',
      '৬': 'ছয়',
      '০৬': 'ছয়',
      '৭': 'সাত',
      '০৭': 'সাত',
      '৮': 'আট',
      '০৮': 'আট',
      '৯': 'নয়',
      '০৯': 'নয়',
      '১০': 'দশ',
      '১১': 'এগারো',
      '১২': 'বার',
      '১৩': 'তের',
      '১৪': 'চৌদ্দ',
      '১৫': 'পনেরো',
      '১৬': 'ষোল',
      '১৭': 'সতের',
      '১৮': 'আঠার',
      '১৯': 'উনিশ',
      '২০': 'বিশ',
      '২১': 'একুশ',
      '২২': 'বাইশ',
      '২৩': 'তেইশ',
      '২৪': 'চব্বিশ',
      '২৫': 'পঁচিশ',
      '২৬': 'ছাব্বিশ',
      '২৭': 'সাতাশ',
      '২৮': 'আঠাশ',
      '২৯': 'ঊনত্রিশ',
      '৩০': 'ত্রিশ',
      '৩১': 'একত্রিশ',
      '২০২০': 'দুই হাজার বিশ',
      '২০২১': 'দুই হাজার একুশ',
      '২০২২': 'দুই হাজার বাইশ',
      '২০২৩': 'দুই হাজার তেইশ',
      '২০২৪': 'দুই হাজার চব্বিশ',
      '২০২৫': 'দুই হাজার পঁচিশ',
      '২০২৬': 'দুই হাজার ছাব্বিশ'
    }

from rasa_sdk.events import SlotSet, ActionReverted, UserUttered, Form, BotUttered
from rasa_sdk.forms import REQUESTED_SLOT

from rasa_sdk.interfaces import Action
from rasa_sdk.events import (
    SlotSet,
    EventType,
    ActionExecuted,
    SessionStarted,
    Restarted,
    FollowupAction,
    UserUtteranceReverted,
    AllSlotsReset,
)
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher

from actions.parsing import (
    parse_duckling_time_as_interval,
    parse_duckling_time,
    get_entity_details,
    parse_duckling_currency,
)

from actions.profile_db import create_database, ProfileDB

from actions.custom_forms import CustomFormValidationAction
from rasa_sdk.types import DomainDict
from actions.converter import is_ascii, BnToEn_Word, BnToEn, amount_in_word, numberTranslate

db_manager = mysql.DBManager()
logger = logging.getLogger(__name__)

# The profile database is created/connected to when the action server starts
# It is populated the first time `ActionSessionStart.run()` is called.

PROFILE_DB_NAME = os.environ.get("PROFILE_DB_NAME", "profile")
PROFILE_DB_URL = os.environ.get("PROFILE_DB_URL", f"sqlite:///{PROFILE_DB_NAME}.db")
ENGINE = sa.create_engine(PROFILE_DB_URL)
create_database(ENGINE, PROFILE_DB_NAME)

profile_db = ProfileDB(ENGINE)

FORM_SLOT_UTTER = {
    'check_balance_form': 'utter_ask_account_number',
    'bKash_form': 'utter_ask_account_number',
    'Card_Activation_form': 'utter_ask_card_number',
    'Card_DeActivation_form': 'utter_ask_card_number',
    'Credit_card_limit_form': 'utter_ask_card_number',
    'cheque_form': 'utter_ask_cheque_number',
}
class ActionSessionStart(Action):
    """Executes at start of session"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_session_start"

    @staticmethod
    def _slot_set_events_from_tracker(
        tracker: "Tracker",
    ) -> List["SlotSet"]:
        """Fetches SlotSet events from tracker and carries over keys and values"""

        # when restarting most slots should be reset
        relevant_slots = ["currency"]

        return [
            SlotSet(
                key=event.get("name"),
                value=event.get("value"),
            )
            for event in tracker.events
            if event.get("event") == "slot" and event.get("name") in relevant_slots
        ]

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        # the session should begin with a `session_started` event
        events = [SessionStarted()]

        events.extend(self._slot_set_events_from_tracker(tracker))

        # create a mock profile by populating database with values specific to tracker.sender_id
        profile_db.populate_profile_db(tracker.sender_id)
        currency = profile_db.get_currency(tracker.sender_id)

        #-----------------------------------------Session Id Exists or Not-------------------------------

        sv=tracker.current_slot_values()
        sv_json_object = json.dumps(sv, indent = 4)
        phone = tracker.get_slot("phone_number")
        print("session started and set everything Null to DB initially")
        account = db_manager.set_session_id(
                tracker.sender_id, phone, sv_json_object
            )
        print(account)

        #---------------------------------------------------------------------------------------------------------------

        # initialize slots from mock profile
        events.append(SlotSet("currency", currency))

        # add `action_listen` at the end
        events.append(ActionExecuted("action_listen"))

        return events


class ActionRestart(Action):
    """Executes after restart of a session"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_restart"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        return [Restarted(), FollowupAction("action_session_start")]

class ActionResetSlots(Action):
    """action_reset_all_slots"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_all_slots"
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print ("slots are being reset")
        return [AllSlotsReset()]

class ActionStop(Action):
    """Executes after interrupt by user"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_interrupt"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        dispatcher.utter_message(response = "utter_interrupt")
        return [FollowupAction("action_restart")]


class WeatherAction(Action):
    """action_weather"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_weather"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])

        currentloop = tracker.active_loop.get('name')
        print(f"Loop name: {currentloop}")

        story_status = tracker.get_slot("Incomplete_Story")
        print(f"Story Incomplete: {story_status}")

        last_action = tracker.latest_action_name
        # last_action = tracker.events
        print(last_action)
        if story_status != True:
            dispatcher.utter_message(response = "utter_weather_query")
            # return [Form(None), SlotSet("requested_slot", None)]
            return []

        else:
            pass
            # dispatcher.utter_message(response = "utter_ask_continue_form")
            # return [FollowupAction('action_check_AC_Number')]
            return [UserUtteranceReverted()]


class Repeat_for_User(Action):
    """Action_Repeat"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_Repeat"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print("User ask for repeat the last utter.")
        intent = tracker.latest_message['intent'].get('name')
        # all_history = tracker.events
        # print(all_history)
        currentloop = tracker.active_loop.get('name')
        print(f"Loop name: {currentloop}")

        story_status = tracker.get_slot("Incomplete_Story")
        print(f"Story Incomplete: {story_status}")

        if currentloop != None:
            return [FollowupAction(currentloop)]
        else:
            dispatcher.utter_message(response = "utter_ask_whatelse")
            print("I'm here")
            # return [Restarted(), FollowupAction("action_session_start")]
            return [UserUtteranceReverted()]
        return []




class ActionCustomFallback(Action):
    """Executes at fallBack"""

    def name(self) -> Text:
        return "action_custom_fallback"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        currentloop = tracker.active_loop.get('name')
        print(f"Loop name: {currentloop}")

        story_status = tracker.get_slot("Incomplete_Story")
        print(f"Story Incomplete: {story_status}")

        fall_counter = 0
        # if(fall_counter in None):
        #     fall_counter=1
        fall_counter =+ 1

        if fall_counter > 3:
            return [FollowupAction("action_session_start")]
            # return [Restarted(), FollowupAction("action_session_start")]

        print("fallback")
        print(fall_counter)
        if story_status == True:
            print("You are inside a story.")
            return[
                    FollowupAction(currentloop),
                ]

        dispatcher.utter_message(response="utter_default")
        return [
                UserUtteranceReverted(),
            ]


class OutOfScope(Action):
    """Action_out_of_scope"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_out_of_scope"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        # global counter
        counter=0
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("out_of_scope")
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        print(type(Input))
        if(counter>1):
            dispatcher.utter_message(response="utter_AT")
            counter=0
            return []

        if tracker.latest_message['intent'].get('name') == "out_of_scope":
            counter=counter+1
            if "কি মেয়ে নাকি ছেলে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_1")
            elif "ঘুরতে যাবে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_2")
            elif "তোমার প্রেমে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_3")
            elif "বিবাহিত" in Input or "বিয়ে" in Input or "অবিবাহিত" in Input or "আনমেরিড" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_4")
            elif "দিনটা কেমন" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_5")
            elif "কি বুদ্ধিমান" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_6")
            elif "প্রিয় পিকআপ লাইন" in Input or "পিকআপ লাইন" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_7")
            elif "কখনো প্রেমে পরেছ" in Input or "প্রেমে পরেছ" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_8")
            elif "আজকে জন্মদিন" in Input or "জন্মদিন" in Input or "বার্থডে" in Input or "জন্মদিন আজকে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_9")
            elif "এলিয়েন" in Input or "এলিয়েন কি সত্যি" in Input or "মহাজাগতিক প্রানী" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_10")
            elif "সিরি" in Input or "সিরি কে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_Siri")
            elif "করটানা" in Input or "কর্টানা" in Input or "করটানা কে" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_Cortana")
            elif "আলেক্সা" in Input or "এলেক্সা কে" in Input or "আলেক্সা কে" in Input or "এলেক্সা" in Input:
                dispatcher.utter_message(response="utter_Out_of_scope_funny_Alexa")
            else:
                dispatcher.utter_message(response="utter_out_of_scope")
        elif 'চেক' in Input or 'চেকবুক' in Input:
            dispatcher.utter_message(response = "utter_cheque_info_ask_new_response")
        else:
            dispatcher.utter_message(response="utter_default")

        return []


class actionDateTime(Action):
    """Action_Current_DateTime"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_Current_DateTime"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        text = tracker.latest_message.get('text')
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print(f"User Input was:{text}")
        months = ["জানুয়ারি", "ফেব্রুয়ারী", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগষ্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"]
        today = date.today()
        now = datetime.datetime.now()
        DATE = today.strftime("%B %d, %Y")
        print("DATE =", DATE)
        year = today.strftime("%Y")
        Y = bangla.convert_english_digit_to_bangla_digit(str(year))
        Y = num_convert.number_to_bangla_words(Y)
        print(Y)
        month = today.strftime("%m")
        month = int(month) - 1
        print("before loop month: ", month)
        Mon = months[month]
        print(Mon)
        day = today.strftime("%d")
        D = bangla.convert_english_digit_to_bangla_digit(str(day))
        D = num_convert.number_to_bangla_words(D)
        print(D)
        print(f"Year: {year}, month: {month}, day: {day}")
        time = now.strftime("%H:%M:%S")
        print("time =", time)

        hour = now.strftime("%H")
        minutes = now.strftime("%M")

        print (f"hour: {hour} and minute: {minutes}")
        if(int(hour)>12):
            hour=str(int(hour) - 12)
        H = bangla.convert_english_digit_to_bangla_digit(str(hour))
        hour = num_convert.number_to_bangla_words(H)
        M = bangla.convert_english_digit_to_bangla_digit(str(minutes))
        Minutes = num_convert.number_to_bangla_words(M)



        d_msg = f"আজকের তারিখ হচ্ছে, {D}, {Mon}, {Y} ।"
        msg = f"এখন সময়, {hour} টা বেজে {Minutes} মিনিট। আমি আর কিভাবে আপনাকে সহায়তা করতে পারি?"
        message = f"এখন সময়, {hour} টা বেজে {Minutes} মিনিট। আজকের তারিখ হচ্ছে, {D}, {Mon}, {Y} ।"
        dispatcher.utter_message(text = msg)

        if "তারিখ" in text:
            pass
            # dispatcher.utter_message(text = d_msg)
        if "সময়" in text:
            pass
            # dispatcher.utter_message(response="utter_card_balance")
        # else:
        #     dispatcher.utter_message(response="utter_card_info")

        return []

class BankLocation(Action):
    """action_bank_location"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_bank_location"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        location_name = tracker.get_slot("location")
        if location_name == None:
            dispatcher.utter_message(response = "utter_bank_location")
            return []
        else:
            if location_name == "মিরপুর" or location_name == "মিরপুরের" or location_name == "মিরপুরে":
                dispatcher.utter_message(response = "utter_bank_location_mirpur")
                return []
            elif location_name == "গুলশান" or location_name == "গুলশানের":
                dispatcher.utter_message(response = "utter_bank_location_gulshan")
                return []
            elif location_name == "শ্যামলী" or location_name == "শ্যামলীর":
                dispatcher.utter_message(response = "utter_bank_location_Shamoli")
                return []
            elif location_name == "বনানী" or location_name == "বনানীর":
                dispatcher.utter_message(response = "utter_bank_location_banani")
                return []
            elif location_name == "বারিধারা" or location_name == "বারিধারার":
                dispatcher.utter_message(response = "utter_bank_location_baridhara")
                return []
            else:
                dispatcher.utter_message(response = "utter_bank_location")
                return []

class ActionGreet(Action):
    """action_greet"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_greet"
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        currentTime = datetime.datetime.now()
        currentTime.hour
        Bank_list = ['ব্রাক ব্যাংক', 'সিটি ব্যাংক', 'ইবিএল', 'স্ট্যান্ডার্ড চার্টার্ড ব্যাংক', 'ব্যাংক এশিয়া']
        Bank_Name = Bank_list[3]
        print(f'Bank Name is {Bank_Name}')
        if 3<= currentTime.hour < 12:
           print('Good morning.')
           dispatcher.utter_message(response="utter_greet_morning", Bank_Name = Bank_list[3])
        elif 12 <= currentTime.hour < 17:
            print('Good afternoon.')
            dispatcher.utter_message(response="utter_greet_afternoon", Bank_Name = Bank_list[3])
        elif 17 <= currentTime.hour < 19:
            print('Good evening.')
            dispatcher.utter_message(response="utter_greet_evening", Bank_Name = Bank_list[3])
        elif 19 <= currentTime.hour < 3:
            print('Good night.')
            dispatcher.utter_message(response="utter_greet_night", Bank_Name = Bank_list[3])
        else:
            print('Good unknown time.')
            dispatcher.utter_message(response="utter_greet")

        return [SlotSet("Incomplete_Story", False)]

class ActionContinue(Action):
    """action_ask_continue"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_ask_continue"
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""

        intent = tracker.latest_message['intent'].get('name')
        intent_text = tracker.latest_message.get('text')

        currentloop = tracker.active_loop.get('name')
        print(f"Loop name: {currentloop}")

        story_status = tracker.get_slot("Incomplete_Story")
        print(f"Story Incomplete: {story_status}")

        if intent == "inform":
            if currentloop != None:
                print('here')
                if(currentloop in FORM_SLOT_UTTER):
                    dispatcher.utter_message(response=FORM_SLOT_UTTER[currentloop])
                return [UserUtteranceReverted()]

        if intent == "Repeat":
            if currentloop != None:
                return [FollowupAction(currentloop)]
            else:
                return [UserUtteranceReverted()]

        if intent == "interrupt":
            dispatcher.utter_message(response = "utter_interrupt")
            return [FollowupAction("action_restart")]

        if story_status == True or currentloop != None:
            if intent == "explain":
                dispatcher.utter_message(response="utter_explain_and_continue")
                return [SlotSet("Continue", True)]
            dispatcher.utter_message(response="utter_ask_continue_form")
            return [
                SlotSet("Continue", True),
                SlotSet("Intent_Text", intent_text),
                SlotSet("Intent_Name", intent),
                ]
        else:
            intent = tracker.latest_message['intent'].get('name')
            return [SlotSet("Continue", False)]

class ActionContinueResponse(Action):
    """action_continue_response"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_continue_response"
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intent = tracker.latest_message['intent'].get('name')
        previous_intent_text = tracker.get_slot("Intent_Text")
        previous_intent = tracker.get_slot("Intent_Name")
        currentloop = tracker.active_loop.get('name')
        print(f"Loop name: {currentloop}")
        print(type(currentloop))
        print(f"previous_intent: {previous_intent}")
        print(f"previous_intent_text: {previous_intent_text}")
        if intent == "affirm":
            return [SlotSet("Continue", False), FollowupAction(currentloop)]
        elif intent == "deny":
            dispatcher.utter_message(response = "utter_ask_whatelse")
            return [Form(None), SlotSet("requested_slot", None), SlotSet("Incomplete_Story", False), SlotSet("Continue", False)]
            # return [Form(None), SlotSet("requested_slot", None), SlotSet("Incomplete_Story", False), SlotSet("Continue", False), UserUttered(previous_intent_text, {"intent": {"name": previous_intent}})]
        else:
            # return [ActionReverted()]
            return [SlotSet("Continue", False), UserUtteranceReverted()]


class ActionExchangeRate(Action):
    """action_Exchange_rate"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Exchange_rate"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        """Executes the action"""
        user_query = tracker.latest_message.get('text')
        print(f"User question is {user_query}")

        # service_name = tracker.get_slot("DPS_FixDepo")
        # print(f"User is asking for {service_name} service.")

        if "DPS" in user_query or "ডিপিএসের ইন্টারেস্ট" in user_query:
            dispatcher.utter_message(response="utter_DPS_InterestRate")
        elif "FixedDeposit" in user_query:
            dispatcher.utter_message(response="utter_FixedDepo_InterestRate")
        else:
            dispatcher.utter_message(response = "utter_exchange_USD")
        return [
            SlotSet("DPS_FixDepo", None),
            SlotSet("Incomplete_Story", False),
            SlotSet("UserInput", None),
            ]



class LandQueries(Action):
    """Action_FAQ_LandQueries"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_FAQ_LandQueries"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])

        print("Action_FAQ_LandQueries")

        Input = tracker.latest_message.get('text')
        print(f"User Input was--:{Input}")

        if 'হোল্ডিং' in Input:
           dispatcher.utter_message(text = "অনলাইনে নামজারি হলে হোল্ডিং খোলার জন্য নামজারি খতিয়ানের কপি নিয়ে ইউনিয়ন ভূমি অফিসে গিয়ে খতিয়ান দেখালে হোল্ডিং খুলে দিবে এবং আপনি অনলাইনে ভূমি উন্নয়ন কর পরিশোধ করতে পারবেন।")
        elif 'নামজারি করতে ২৫ বছরের মালিকানা স্বত্ব প্রদান করা বাধ্যতামূলক কিনা?' in Input:
            dispatcher.utter_message(text = "নামজারী করতে পঁচিশ বছরের মালিকানা স্বত্ব বাধ্যতামূলক নয়। কিন্তু সর্বশেষ রেকর্ড বা সর্বশেষ নামজারি হতে মালিকানা স্বত্ব পরিবর্তনের প্রমানপত্র বা বায়া দলিলাদি দেয়া বাধ্যতামূলক।")
        elif 'আমার জমি অনলাইনে নামজারির আবেদন করা আছে, খতিয়ান পাবো কি করে' in Input:
            dispatcher.utter_message(text="চলমান ই-মিউটেশন বা নামখারিজের মামলায় সামজারি মঞ্জুর হলে ডিসিআর  ফী ১,১০০ টাকা পরিশোধ করলে অনলাইনেই চালান প্রক্রিয়া শুরু হবে। স্বয়ংক্রিয়ভাবে চালান পরিশোধিত  হলে ল্যান্ড মিনিস্ত্রি লিঙ্ক এ গিয়ে আবেদন ট্র্যাকিং করে খতিয়ান প্রিন্ট এবং ডিসিআর প্রিন্ট কপিটি পাবেন।")
        elif 'কোন ভূমি অনলাইন নামজারি আবেদন করলে নামজারি খতিয়ান/পর্চা  বা পর্চা  কি অনলাইনে পাওয়া যাবে' in Input:
            dispatcher.utter_message(text="চলমান ই-মিউটেশন বা নামখারিজের মামলায় সামজারি মঞ্জুর হলে ডিসিআর  ফী ১,১০০ টাকা পরিশোধ করলে অনলাইনেই চালান প্রক্রিয়া শুরু হবে। স্বয়ংক্রিয়ভাবে চালান পরিশোধিত  হলে ল্যান্ড মিনিস্ত্রি লিঙ্ক এ গিয়ে আবেদন ট্র্যাকিং করে খতিয়ান প্রিন্ট এবং ডিসিআর প্রিন্ট কপিটি পাবেন।")
        elif 'অনলাইনে নামজারি খতিয়ান/পর্চা কি করে পাবো' in Input:
            dispatcher.utter_message(text="পূর্বের কোন ম্যানুয়াল কোন নামজারি কেসের অনলাইন পর্চা/খতিয়ান সংগ্রহ করতে হয় তবে  ই পর্চা ডট গভ ডট বিডি তে গিয়ে নামজারি খতিয়ান বাটনে ক্লিক করে তথ্য দিয়ে সংগ্রহ করতে হবে।নামজারি খতিয়ান অনলাইনে পাওয়া যাবে যদি তা অনলাইনে আপলোড থাকে। অন্যথায় জেলা রেকর্ড রুমে আবেদন করে সংগ্রহ করতে হবে।")
        elif 'জমির মালিকানা সূত্র কি কি ভাবে হতে পারে' in Input or 'মালিকানা সূত্র কি কি ভাবে হতে পারে' in Input or 'মালিকানা কি কি ভাবে হতে পারে' in Input or 'মালিকানা সূত্র কি কি' in Input:
            dispatcher.utter_message(text = "মালিকানা সুত্রগুলো হল, ক্রয়, ওয়ারিস, হেবা, ডিক্রি, নিলাম, বন্দোবস্ত, এবং অধিগ্রহণ সূত্র")
        elif 'নামজারি না হলে' in Input or 'বাতিল হইছে' in Input or 'নামজারি আবেদন না মঞ্জুর' in Input or 'আবেদন না মঞ্জুর' in Input or 'না মঞ্জুর' in Input or 'নামঞ্জুর' in Input or 'মঞ্জুর না' in Input or 'মঞ্জুর হয় নাই' in Input or 'মঞ্জুর' in Input or 'নামজারির আবেদন নামঞ্জুর' in Input or 'আবেদন নামঞ্জুর' in Input or 'নামজারি না হইলে' in Input:
            if 'হোল্ডিং নাম্বার' in Input:
                dispatcher.utter_message(text = "হোল্ডিং নম্বরটি সংশ্লিষ্ট ইউনিয়ন ভূমি অফিস থেকে দেওয়া হয়ে থাকে। অনুগ্রহ করে আপনি ইউনিয়ন ভূমি অফিসে যোগাযোগ করবেন।")
            elif 'জেলা আদালতে' in Input or 'অতিরিক্ত জেলা প্রশাসক' in Input or 'অতিরিক্ত জেলা প্রশাসকের' in Input or 'এডিসি' in Input or 'এডিসির' in Input or 'জেলা প্রশাসকের' in Input or 'ডিসিআর আদালতে' in Input:
                dispatcher.utter_message(text = "আদেশের ষাট দিনের মধ্যে বা উপযুক্ত কারণ থাকলে বিভাগীয় কমিশনারের নিকট ঐ নামজারী আদেশের বিরুদ্ধে আপিল বা মামলা দায়ের করতে হয়।")
            elif 'বিভাগীয় আদালতে' in Input or 'বিভাগীয় কমিশনারের' in Input or 'বিভাগ গিয়েও কমিশন' in Input or 'বিভাগীয় কমিশনার' in Input or 'কমিশনারের' in Input or 'কমিশনার' in Input or 'কমিশনের আদালতে' in Input:
                dispatcher.utter_message(text = "আদেশের নব্বই দিনের মধ্যে বা উপযুক্ত কারণ থাকলে ঢাকায় ভূমি আপিল বোর্ডের নিকট ঐ নামজারী আদেশের বিরুদ্ধে আপিল বা মামলা দায়ের করতে হয়।")
            elif 'ভুলের কারণে' in Input or 'কারণে' in Input:
                dispatcher.utter_message(text = "নামজারি আবেদন না মঞ্জুর হয় যে সকল ভুলের কারণে সেগুলো জানতে, ভূমি মন্ত্রণালয় এর ওয়েবসাইট দেখুন, বিস্তারিত দেয়া আছে।")
            else:
                dispatcher.utter_message(text = "কাগজপত্রে ঘাটতির জন্য বা অসম্পূর্ণ আবেদনের জন্য তদন্ত ও শুনানীর পূর্বেই নামজারি আবেদন বাতিল হলে বাতিলের কারণ নির্নয় করে উক্ত কারণ দূরীভূত করে পুনরায় আবেদন করতে হবে।")
        elif 'নামজারি থাকতে হবে কিনা' in Input or 'ভূমি মালিকের ওয়ারিশ সম্পত্তি বণ্টন করা হয়নি। উক্ত সম্পত্তি ওয়ারিশদের মধ্যে একজন বিক্রয় করতে চাইলে তার নামজারি থাকতে হবে কিনা' in Input or 'সম্পত্তি ওয়ারিশদের মধ্যে একজন বিক্রয় করতে চাইলে তার নামজারি থাকতে হবে কিনা' in Input or 'সম্পত্তি ভূমি মালিক দানপত্র করতে চাইলে তার নামজারি থাকতে হবে কিনা' in Input or 'সম্পত্তি ভূমি মালিক হেবা করতে চাইলে তার নামজারি থাকতে হবে কিনা' in Input:
            dispatcher.utter_message(text = "নামজারী থাকতে হবে। সকল ধরণের কাজের জন্যই লাগবে। এটা প্রমাণ করবে যে ঐ জমির প্রকৃত মালিক বা ওয়ারিশ।")
        elif 'জমির রেকর্ড এর ধারাবাহিকতা' in Input or 'রেকর্ড এর ধারাবাহিকতা' in Input:
            dispatcher.utter_message(text = "পূর্ববর্তী রেকর্ডীয় মালিক হতে উত্তরাধিকার বা হস্তান্তর দলিল সূত্রে মালিকানা পরিবর্তনের প্রমাণ পত্র পরবর্তী রেকর্ডের সাথে মিলিয়ে জমির রেকর্ডের ধারাবাহিকতা জানা যাবে।")
        elif 'ওয়াকফ বা দেবোত্তর জমি নামজারি করা যাবে কিভাবে' in Input or 'ওয়াকফ বা দেবোত্তর জমি নামজারি করা' in Input or 'ওয়াকফ বা দেবোত্তর জমি নামজারি' in Input or 'ওয়াকফ জমি নামজারি করা যাবে কিভাবে' in Input or 'ওয়াকফ জমি নামজারি করা' in Input or 'ওয়াকফ জমি নামজারি' in Input or 'দেবোত্তর জমি নামজারি করা যাবে কিভাবে' in Input or 'দেবোত্তর জমি নামজারি করা' in Input or 'দেবোত্তর জমি নামজারি' in Input:
            dispatcher.utter_message(text = "ওয়াকফ ও দেবোত্তর সম্পত্তি সাধারণভাবে বিক্রয় বা হস্তান্তর নিষিদ্ধ । অপরিহার্য প্রয়োজনে ওয়াকফ সম্পত্তির কিছু অংশ বিক্রয় বা হস্তান্তর করতে হলে ওয়াকফ প্রশাসকের নিকট অবেদন করতে হয়। বিস্তারিত জানতে ভূমি মন্ত্রণালয়ের ওয়েব সাইট এ দেখতে পারেন।")
        elif 'খাস জমি কী নামজারি করা যায়' in Input or 'খাস জমি নামজারি' in Input or ('খাস জমি' in Input and 'নামজারি' in Input):
            dispatcher.utter_message(text = "খাস জমি ক্রয় বিক্রয় বা হস্তান্তর করা যায় না বিধায় তৎসূত্রে নামজারি করা যায় না। কিন্তু সরকার খাস জমি কাউকে স্থায়ী বন্দোবস্ত দিলে তার নামে নামজারি করা যায় এবং এইরূপ স্থায়ী বন্দোবস্তকৃত খাসজমি কেবলমাত্র উত্তরাধিকারসূত্রে নামজারি করা যায়।")
        elif 'নামজারি আবেদন দ্রুত নিষ্পত্তি করার কোনো সুযোগ আছে কি' in Input or 'নামজারি আবেদন দ্রুত নিষ্পত্তি' in Input or 'আবেদন দ্রুত নিষ্পত্তি' in Input:
            dispatcher.utter_message(text = "নামজারি আবেদন দাখিল, তদন্ত ও শুনানীর জন্য প্রয়োজনীয় সময় আবশ্যক। জনগণকে দ্রুত সেবা প্রদান নিশ্চিত করতে ভূমি মন্ত্রণালয়ের নির্দেশনামতে ২৮ দিনের মধ্যে নামজারি আবেদন নিস্পত্তি হয়ে থাকে। তদন্ত ও শুনানীতে সময় কমিয়ে এর কম সময়ে নামজারি করা যেতে পারে।")
        elif 'অনলাইনের পরিবর্তে ম্যানুয়াল পদ্ধতিতে আবেদন করার সুযোগ আছে কি' in Input or 'ম্যানুয়াল পদ্ধতিতে আবেদন করার সুযোগ' in Input:
            dispatcher.utter_message(text = "বর্তমানে ই-নামজারি ব্যতীত কোনো ধরণের ম্যানুয়াল পদ্ধতিতে আবেদন করার সুযোগ নাই। আপনাকে কি আর কোন সহায়তা করতে পারি")
        elif 'আমি অনলাইন অর্থ প্রদানের ক্ষেত্রে কিছু সমস্যা পেয়েছি' in Input or 'অনলাইন অর্থ প্রদানের ক্ষেত্রে কিছু সমস্যা' in Input:
            dispatcher.utter_message(text = "অনলাইনে অর্থ প্রদানে সমস্যা হলে ভূমি মন্ত্রণালয়ে হটলাইন এক ছয় এক দুই দুই নম্বরে জানাতে পারবেন। ধন্যবাদ, আপনাকে কি আর কোন সহায়তা করতে পারি")
        elif 'নামজারি করার জন্য ফি পরিশোধ প্রক্রিয়া কি কি' in Input or 'নামজারি করার ফি পরিশোধ প্রক্রিয়া' in Input or 'নামজারি করার জন্য ফি পরিশোধ প্রক্রিয়া কি' in Input:
            dispatcher.utter_message(text = "আবেদন সাবমিট করার সময় ফি প্রদানের অপশন আসবে। যেকোন একটি পেমেন্ট ইন্সট্রুমেন্ট ব্যাবহার করে পেমেন্ট করতে পারবেন। আবেদন সাবমিট করে যদি পরবর্তীতে ফি প্রদান করতে চান তাহলেও করতে পারবেন। ভূমি মন্ত্রণালয় এর ওয়েবসাইট দেখুন, বিস্তারিত দেয়া আছে।")
        elif 'অনলাইন শুনানির সময় পরিবর্তন করা যাবে কি' in Input or 'শুনানির সময় পরিবর্তন করা যাবে' in Input or 'শুনানির সময় পরিবর্তন' in Input:
            dispatcher.utter_message(text = "নাগরিক কর্নার থেকে সিস্টেমের মাধ্যমে শুনানির সময় পরিবর্তন করা যাবে না। তবে, শুনানির তারিখে হাজির হতে না পারলে সহকারী মকমিশনার(ভূমি)র সাথে যোগাযোগ করে পরবর্তী সুবিধাজনক তারিখে শুনানি গ্রহণের সুযোগ আছে।")
        elif 'আমার নামজারি আবেদনের অগ্রগতি কিভাবে দেখতে পারব' in Input or 'নামজারি আবেদনের অগ্রগতি কিভাবে দেখতে' in Input or 'নামজারি আবেদনের অগ্রগতি' in Input:
            dispatcher.utter_message(text = "ভূমি মন্ত্রণালয় এর ওয়েবসাইটে গিয়ে আবেদন ট্রাকিং করলে বিস্থারিত জানা যাবে। বিভাগ, আবেদন নম্বর, আবেদনে প্রদানকৃত জাতীয় পরিচয়পত্র নম্বর দিয়ে ট্রাকিং করতে পারবেন।")
        elif 'মূল খতিয়ান নিতে কি ভূমি অফিসে যেতে হবে' in Input or 'খতিয়ান নিতে কি ভূমি অফিসে যেতে হবে' in Input:
            dispatcher.utter_message(text = "অনলাইনে ডিসিআর ফী এগারো শত টাকা পরিশোধ করলে অনলাইনেই চালান প্রক্রিয়া শুরু হবে। স্বয়ংক্রিয়ভাবে চালান পরিশোধিত হলে ভূমি মন্ত্রণালয় এর ওয়েবসাইটে গিয়ে আবেদন ট্র্যাকিং করে খতিয়ান প্রিন্ট এবং ডিসিআর প্রিন্ট কপিটি পাবেন। তাই আপনাকে ভূমি অফিসে গিয়ে কোনো ম্যানুয়াল খতিয়ান সংগ্রহ করতে হবে না।")
        elif 'নামজারি খতিয়ান পাওয়ার পরে খতিয়ানে কোন ভুল তথ্য পেলে তা সংশোধনের' in Input or 'চূড়ান্ত নামজারি খতিয়ান পাওয়ার পরে খতিয়ানে কোন ভুল তথ্য পেলে তা সংশোধনের উপায় কি' in Input or 'খতিয়ানে কোন ভুল তথ্য' in Input:
            dispatcher.utter_message(text = "খতিয়ানসহ সহকারি কমিশনার (ভূমি) অফিসে যোগাযোগ করতে হবে। সহকারি কমিশনার (ভূমি) খতিয়ানের তথ্য সংশোধন করার জন্য উদ্যোগ গ্রহণ করবেন এবং এক্ষেত্রে সংশোধনের জন্য কোনো ফী প্রয়োজন নেই।")
        elif 'জমির বিপরীতে খাজনা বকেয়া বা সার্টিফিকেট মামলা আছে কিনা' in Input or 'জমির বিপরীতে খাজনা বকেয়া' in Input or 'জমির বিপরীতে মামলা আছে কিনা' in Input or 'জমির বিপরীতে কোনো মামলা আছে কিনা' in Input:
            dispatcher.utter_message(text = "ইউনিয়ন ভূমি অফিস ও উপজেলা ভূমি অফিস ছাড়া সার্টিফিকেট মামলা দেখার সুযোগ নেই। অবশ্যই ইউনিয়ন ভূমি অফিসে তলব বাকি রেজিস্টারে দেখতে হবে সেখানে ভূমি উন্নয়ন কর বকেয়ার কোন তথ্য আছে কিনা? সার্টিফিকেট মামলা আছে কিনা তা সরাসরি ইউনিয়ন ভূমি অফিস ও উপজেলা ভূমি অফিসে গিয়ে জানা যাবে।")
        elif 'মামলা' in Input or 'জমির বিপরীতে কোনো মামলা আছে কিনা' in Input:
            dispatcher.utter_message(text = "জমি নিয়ে মামলা আছে কিনা তা তৃতীয় পক্ষের দাপ্তরিকভাবে জানার সুযোগ কম। সংশ্লিষ্ট এলাকায় খোঁজ নিয়ে জানতে পারেন। তাছাড়া যখন নিশ্চিত হবেন যে অমুক কোর্টে একটি মামলা আছে, তখন সংশ্লিষ্ট কোর্টের সেরেস্তায় গিয়ে জমির তফসিল দিয়ে তল্লাশী দিয়ে এ বিষয়ে জানতে পারেন। তাছাড়া মামলায় সরকারকে পক্ষ করা হলে ইউনিয়ন ভূমি অফিস নোটিশ পায়, এক্ষেত্রে ইউনিয়ন ভূমি অফিস থেকে তথ্য জানতে পারেন।")
        elif 'জমি খাস খতিয়ান ভুক্ত' in Input or 'সায়রাত মহাল ভুক্ত' in Input or 'পাবলিক ইজমেন্ট সম্পর্কিত' in Input or 'অর্পিত সম্পত্তি ভুক্ত' in Input:
            dispatcher.utter_message(text = "উপজেলা ও ইউনিয়ন ভূমি অফিস হতে জানা যাবে।")
        elif 'ওয়ারিশ সনদ ও উত্তারিধিকার সনদ এর মধ্যে পার্থক্য কি' in Input or ('ওয়ারিশ সনদ' in Input and 'উত্তারিধিকার সনদ' in Input and 'পার্থক্য' in Input):
            dispatcher.utter_message(text = "কোন পার্থক্য নেই। দুটোই সেইম।")
        elif ('উত্তারিধিকার সনদ' in Input and 'মেয়াদ' in Input) or ('ওয়ারিশ সনদ' in Input and 'মেয়াদ' in Input) or 'ওয়ারিশ সনদ এর মেয়াদ কত দিন' in Input or 'ওয়ারিশ সনদ এর মেয়াদ শেষ হওয়ার পরেও ওয়ারিশ সনদ ব্যাবহার করা যাবে' in Input or 'উত্তারিধিকার সনদ এর মেয়াদ কত দিন' in Input or 'উত্তারিধিকার সনদ এর মেয়াদ শেষ হওয়ার পরেও উত্তারিধিকার সনদ ব্যাবহার করা যাবে' in Input:
            dispatcher.utter_message(text = "ওয়ারিশ সনদ বা উত্তারিধিকার সনদ এর মেয়াদ তিন মাস হতে হয়। আপনআর যদি উত্তারিধিকার সনদ বা ওয়ারিশ সনদ তিন মাসের আগের হয় তাহলে নতুন করে এই সনদ গুলো সংগ্রহ করতে হবে।")
        elif ('নামজারি খতিয়ান বা পর্চা' in Input or 'নামজারি খতিয়ান' in Input or 'নামজারি পর্চা' in Input) and 'অনলাইনে' in Input:
            dispatcher.utter_message(text = "অনলাইনে নামজারি আবেদন সহকারী কমিশনার, ভূমি, মঞ্জুর করলে নামজারি খতিয়ান বা পর্চা অনলাইনে যাঁচাই করা যাবে তবে মূল নামজারি খতিয়ান, পর্চা টি উপজেলা ভূমি অফিস থেকে পাওয়া যাবে।")
        elif ('সার্টিফাইড খতিয়ানের' in Input or 'সার্টিফাইড খতিয়ান' in Input) and ('আবেদন' in Input or 'ভেলিভারি' in Input or 'ডেলিভারি' in Input or 'ডেলিভারি ডেট' in Input):
            dispatcher.utter_message(text = "অনুগ্রহ করে ই-পর্চা ডট গব ডট বিডি, এই ওয়েবসাইটের মাধ্যমে আপনি সাপোর্ট টিকেট সম্পন্ন করবেন।")
        elif 'আর এস খতিয়ান কিভাবে' in Input or 'আর এস পর্চা কিভাবে' in Input or ('আর এস খতিয়ান' in Input or 'আর এস পর্চা' in Input):
            dispatcher.utter_message(text = "অনলাইনে আর এস খতিয়ান, পর্চা দেখতে অনুগ্রহপূর্বক, ই পরচা ডট গব ডট বিডি, এই ওয়েবসাইট এ প্রবেশ করুন। এরপর নাগরিক কর্নার থেকে খতিয়ান, পর্চা আবেদন অপশনটি নির্বাচন করে, অনলাইন আবেদন ফরম এ গিয়ে ফরমের যাবতীয় তথ্যাদি দিয়ে অনুসন্ধানের মাধ্যমে উক্ত বিষয়টি সম্পর্কে জানতে পারবেন।")
        elif 'হোল্ডিং খোলা' in Input or 'জোত খোলা' in Input:
            dispatcher.utter_message(text = "অনলাইনে নামজারি হলে হোল্ডিং খোলার জন্য নামজারি খতিয়ানের কপি নিয়ে ইউনিয়ন ভূমি অফিসে গিয়ে খতিয়ান দেখালে হোল্ডিং খুলে দিবে এবং আপনি অনলাইনে ভূমি উন্নয়ন কর পরিশোধ করতে পারবেন।")
        elif 'ডিসি আর ফি' in Input or 'ডিসি আর' in Input:
            dispatcher.utter_message(text = "আপনি যদি অনলাইনে নামজারির আবেদন করে থাকেন ডিসি আর পেমেন্টটি অনলাইনে পরিশোধ করতে পারবেন। আর যদি ম্যানুয়ালি করে থাকেন এবং উপজেলা ভূমি অফিস থেকে সংগ্রহ করতে পারবেন। অতিরিক্ত টাকা চাওয়া হয় আপনি চাইলে আমাদের কাছে অভিযোগ করতে পারেন।")
        elif ('খতিয়ান সংশোধন' in Input or 'পর্চা সংশোধন' in Input) and ('আদালতে মামলা' in Input or 'মামলা' in Input):
            dispatcher.utter_message(text = "খতিয়ান বা পর্চা সংশোধন এর জন্য আদালতে মামলা দায়ের করা যায়। আদালত রেকর্ড সংশোধন করেন না। তিনি শুধু সংশোধন করার বা না করার আদেশ দেন। পরবর্তীতে এ আদেশ দিয়ে সহকারী কমিশনার (ভূমি) অফিসে  মিস মামলা করে রেকর্ড সংশোধন করিয়ে নিতে হয়। তাছাড়া আপনার পক্ষে রায় ডিক্রি থাকলে পূর্ববর্তী মালিকের নামে রেকর্ড থাকলে স্বত্বের কোন অসুবিধা নেই।")
        elif 'অনলাইনে কিভাবে পুরাতন দলিল সম্পর্কে' in Input or ('অনলাইনে' in Input and 'পুরাতন দলিল' in Input):
            dispatcher.utter_message(text = "অনলাইনে দলিল দেখার সুযোগ নেই, দলিল সংক্রান্ত যে কোনো তথ্য জানতে আপনাকে যে উপজেলা সাব রেজিষ্ট্রার অফিসে রেজিস্ট্রেশন করা হয়েছে সেখানে মোহরারের সাথে যোগাযোগ করে জানতে পারেন বা নকল তুলতে পারেন।")
        elif 'জমির মালিকের তথ্য কি অনলাইনে দেখা যাবে' in Input or 'জমির মালিকের তথ্য' in Input:
            dispatcher.utter_message(text = "অনলাইনে জমির মালিকের তথ্য দেখার সুযোগ রয়েছে। অনলাইনে জমির মালিকের তথ্য দেখার জন্য, ই পরচা ডট গব ডট বিডি, এই ওয়েব সাইটটিতে প্রবেশ করে খতিয়ান, পর্চা  অনুসন্ধান অপশনটি বাছাই করতে হবে, এরপর সেখানে উল্লেখিত সকল তথ্য সঠিকভাবে পূরণ করে জমির মালিকের তথ্য দেখতে পারেন। অন্যের জমির তথ্য তার সম্মতি ছাড়া দেখা উচিত না।")
        elif 'নামজারির জন্য অনলাইনে সব ডকুমেন্ট জমা দেয়া হয়েছে, সেগুলো আবার সরাসরি অফিসে যেয়ে হার্ডকপি জমা দিতে হবে কেন' in Input or 'ই নামজারি আবেদনে কাগজাদির সফট কপি দেয়া হলেও শুনানীতে হার্ড কপি বা আসল কাগজাদি চাচ্ছে' in Input:
            dispatcher.utter_message(text = "সেক্ষেত্রে অনলাইনে সব কার্যক্রম চললেও পাশাপাশি দাখিলকৃত কাগজাদির সঠিকতা যাঁচাইয়ের জন্যকাগজপত্রের হার্ডকপি দাখিল করা এবং শুনানিকালে হার্ডকপিসহ হাজির হওয়ার নিয়ম চালু রয়েছে।")
        elif 'জন্মনিবন্ধন' in Input or 'এন,আই,ডি' in Input or 'এনআইডি' in Input or 'এন আই ডি' in Input or 'পাসপোর্ট' in Input:
            dispatcher.utter_message(text = "পাসপোর্ট কার্ডের নম্বর দিয়ে নামজারির জন্য আবেদন চালু নেই। এনআইডি বা জন্মনিবন্ধন না থাকলে পাসপোর্ট হয়না। অনুগ্রহ করে এনআইডি বা জন্মনিবন্ধন সংগ্রহ করুন।")
        elif 'ফি কিভাবে অনলাইনে পরিশোধ করব' in Input or 'নামজারি ফি কিভাবে অনলাইনে পরিশোধ করব' in Input:
            dispatcher.utter_message(text = "আপনার অনলাইন পেমেন্টটি করার জন্য আপনার কাছে মেসেজ যাবে, আপনি মোবাইল পেমেন্ট এ্যাপস, কার্ড, ব্যাংকের মাধ্যমে জমা দিতে পারবেন।")
        elif ('পেমেন্ট' in Input and 'দাখিলা' in Input) or ('পেমেন্ট করলে কতদিন পরে দাখিলা পাবো' in Input):
            dispatcher.utter_message(text = " অনলাইনে ভূমি উন্নয়ন কর পরিশোধ করে থাকলে দাখিলাটি পেতে বাহাত্তর ঘন্টা সময় প্রয়োজন পড়ে।")
        elif 'জন্ম সনদ দিয়ে কিভাবে অনলাইন পেমেন্ট  করব' in Input or 'জন্ম সনদ দিয়ে অনলাইন পেমেন্ট' in Input:
            dispatcher.utter_message(text = "আপনার অনলাইন পেমেন্টটি করার জন্য অবশ্যই আপনার এন আই ডি নাম্বারটি প্রয়োজন পড়বে কিংবা আপনার প্রতিনিধির মাধ্যমে পেমেন্টটি করতে হবে।")
        elif 'চলমান জরীপের তথ্য কিভাবে পাব' in Input or 'জরীপের তথ্য' in Input:
            dispatcher.utter_messgae(text = "উপজেলা পর্যায়ে সেটেলমেন্ট অফিস বা জোনাল সেটেলমেন্ট অফিসে অনুগ্রহ করে যোগাযোগ করার চেষ্টা করবেন।")
        elif 'অনলাইনে বিএস খতিয়ান চেক করা যায় কিভাবে' in Input or 'অনলাইনে বিএস পর্চা চেক করা যায় কিভাবে' in Input or 'অনলাইনে বিএস খতিয়ান চেক' in Input:
            dispatcher.utter_message(text = "অনলাইনে বিএস খতিয়ান, পর্চা চেক করা সম্ভব। পর্চা দেখতে অনুগ্রহপূর্বক, ই পরচা ডট গব ডট বিডি ভিজিট করুন, এই ওয়েবসাইটটিতে প্রবেশ করে আপনার খাতিয়ানের তথ্য সঠিক ভবে দেয়ার মাধ্যমে আবেদন করে খাতিয়ানটি পেতে পারবেন।")
        elif 'দলিল কার নামে আছে' in Input:
            dispatcher.utter_message(text = "বর্তমানে দলিল বিষয়ের অনলাইন এ তথ্যটি জানা সম্ভব নয় । অনুগ্রোহপূর্বক দলিল বিষয়ে তথ্য পেতে সরাসরি উপজেলা সাব রেজিস্টার অফিস এ পরিচিত দলিল লেখকদের সাথে কথা বলুন। তবে দলিলের তথ্যের জন্য দলিল নম্বর ও সন জানা প্রয়োজন।")
        elif 'অনলাইনে ভুমি উন্নয়ন কর দিয়েছি কিন্তু এখন কিভাবে দাখিলা পাব' in Input:
            dispatcher.utter_message(text = "অনলাইনে ভূমি উন্নয়ন কর বা খাজনা,ভূমি উন্নয়ন কর দেয়া হলে অটোমেটেড চালানের কপি পাওয়া যাবে অনলাইনে, তার প্রিন্ট নিয়ে ইউনিয়ন ভূমি অফিসে গিয়ে দেখালে অফিসার যাঁচাই করে ই দাখিলা প্রদান করবেন। চালান প্রাপ্তি দুই বা তিন দিন পরে যাবেন।")
        elif 'যদি অনলাইন থেকে ডিসিআর পেমেন্ট করি তাহলে সাথে সাথে খতিয়ান কপি পাবো নাকি' in Input or 'যদি অনলাইন থেকে ডিসিআর পেমেন্ট করি তাহলে সাথে সাথে পর্চা কপি পাবো নাকি' in Input:
            dispatcher.utter_message(text = "আপনি যখন আবেদন করবেন সম্ভাব্য তারিখটি আপনাকে জানিয়ে দেয়া হবে।")
        elif 'ই-নামজারী অনলাইন করার ক্ষেত্রে যারা প্রবাসি তাদের এনইডি নেই সেক্ষেত্রে উপায় কি' in Input or 'প্রবাসী যার ভোটার আইডি কার্ড নেই, সেক্ষেত্রে অনলাইনে ভূমি উন্নয়ন কর কিভাবে পরিশোধ করতে হবে' in Input or 'প্রবাসীরা পাসপোর্ট দিয়ে কিভাবে অনলাইনে ভূমি উন্নয়ন কর কিভাবে পরিশোধ' in Input or ('পাসপোর্ট' in Input and 'ভূমি উন্নয়ন কর' in Input):
            dispatcher.utter_message(text = "ভোটার আইডি কার্ড না থাকলে বর্তমানে অনলাইন ভূমি উন্নয়ন কর নিবন্ধন করা সম্ভব নয়। এইক্ষেত্রে ভোটার আইডি কার্ড তৈরীর পদক্ষেপ গ্রহন করুন অন্যথায় পাসপোর্ট, জন্ম নিবন্ধন বা অন্য কোনো দলিলের মাধ্যমে নিবন্ধন কাজ চালু হওয়া পর্যন্ত অপেক্ষা করুন।")
        elif 'সকল উপজেলায় কী নামজারি ফি অনলাইনে দেওয়া যায়' in Input:
            dispatcher.utter_message(text = "সকল উপজেলায় নামজারি ফি অনলাইনে দেওয়া যায়।")
        elif 'নামজারীর' in Input and 'অনলাইন শুনানি' in Input:
            dispatcher.utter_message(text = "নামজারীর জন্য অনলাইন শুনানি সম্ভব। এক্ষেত্রে বিষয়টি এসি ল্যান্ড মহোদয়কে অভিহিত করতে হবে।")
        elif ('খাস জমি বের করতে পারবো' in Input) or ('খাস জমি' in Input and ('খুঁজে' in Input or 'খুঁজা' in Input)):
            dispatcher.utter_message(text = "অনলাইনে খাস জমি দেখার সুযোগ নেই। এক্ষেত্রে আপনাকে উপজেলা ভূমি অফিসে যোগাযোগ করতে হবে।")
        elif 'অনলাইন ডিসিআর' in Input or ('ডিসিআর' in Input and 'অনলাইনে' in Input):
            dispatcher.utter_message(text = "দুঃখিত এক্ষেত্রে অনলাইন ডি সি আর পাবার সুযোগ নেই।")
        elif 'দাগ, পরিমান ও নামের ভূল সংশোধনের' in Input or 'নামের ভূল সংশোধনের' in Input or 'পরিমানের ভূল সংশোধনের' in Input:
            dispatcher.utter_message(text="নামজারীর আদেশের ৩০ দিনের মধ্যে বা উপযুক্ত কারণ থাকলে তার পরেও অতিরিক্ত  (ভূমি)র  নিকট ঐ নামজারী আদেশ বাতিলের জন্য  রিভিউ/মিস কেস বা মামলা দায়ের করতে হয়।")
        else:
            dispatcher.utter_message(response = "utter_ask_rephrase")

        return []


class InfoCorrection(Action):
    """action_Information_Correction"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Information_Correction"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if 'আমার আবেদনে তথ্য প্রদানে ভুল করেছি এবং আবেদন ইতিমধ্যে জমা দেওয়া হয়েছে' in Input or 'আবেদনে তথ্য প্রদানে ভুল করেছি এবং আবেদন ইতিমধ্যে জমা দেওয়া হয়েছে' in Input or 'আমার আবেদনে তথ্য প্রদানে ভুল করেছি এবং আবেদন ইতিমধ্যে জমা দেওয়া হয়েছে আমি কী করতে পারি' in Input:
            dispatcher.utter_message(text = "সহকারি কমিশনার এই আবেদনটি প্রক্রিয়া শুরু না করা পর্যন্ত অনলাইনে আবেদন তথ্য সংশোধন করা যাবে। প্রক্রিয়া শুরু হয়ে গেলে আবেদনকারি আর সংশোধনের সুযোগ পাবেন না, তবে আবেদনকারী শুনানির সময় সহকারি কমিশনার মহোদয়ের নিকট তথ্য সংশোধনের আবেদন করতে পারবেন।")
        elif 'অনলাইন' in Input and ('ভুল' in Input or 'বানান ভুল' in Input or 'দাগ নম্বর ভুল' in Input or 'জমির পরিমান ভুল' in Input):
            dispatcher.utter_message(text = "অনলাইন নামজারিতে অনলাইন খতিয়ানে কোন ভুল হলে তখনই আবেদন দিয়ে সহকারি কমিশনার ভূমির দৃষ্টিতে আনতে হবে, সহকারি কমিশনার ভূমি মিস কেস বা রিভিউ মামলা করে কাগজাদি যাঁচাই করে ভূল সংশোধনের আদেশ দিয়ে পূর্বের খতিয়ান বাতিল করে নতুন সংশোধিত খতিয়ান জারি করবেন।")
        elif 'অর্ডার চূড়ান্ত' in Input and ('তথ্য নির্ভুল' in Input or 'তথ্য সঠিক' in Input):
            dispatcher.utter_message(text = "ইউনিয়ন ভূমি সহকারি কর্মকর্তা যখন সহকারি কমিশনারএর কাছে প্রতিবেদন প্রেরণ করেন তখন নাগরিক কর্নার থেকে আবেদন ট্রাকিং করে আবেদনকারি খসড়া খতিয়ানের সকল তথ্য দেখতে পারেন। এখানে যদি কোন ভুল থাকে সেটা শুনানির সময় সহকারি কমিশনার কে অবগত করবেন। তখন সহকারি কমিশনার এটি সংশোধন করে দিবেন।")
        else:
            dispatcher.utter_message(response = "utter_default")


        return []

class NamzariInfo(Action):
    """action_Namzari_Info"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Namzari_Info"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if 'বিনিময় সম্পত্তি' in Input and 'নামজারি' in Input:
            dispatcher.utter_message(text = "বিনিময় সম্পত্তি যথাযথভাবে যাঁচাই ছাড়া জেলা প্রশাসক অনুমোদন দেন না তারপরেও সহকারি কমিশনার ভূমি অনুমোদন ডিসি অফিসে যাঁচাইয়ের পরে সঠিক পেলে  নামজারি মঞ্জুর করতে পারেন ন। বিনিময় সম্পত্তি, বিনিময় অনুমোদন না থাকলে  নামজারি হবে না।")
        elif 'রেজিস্টার্ড দলিল' in Input and 'নামজারি' in Input:
            dispatcher.utter_message(text = "নামজারির সময় সহকারি কমিশনার ভূমি জমির মালিকানার ধারাবাহিকতা আছে কি না দেখে থাকেন।জরিপ রেকর্ড পর্যন্ত মালিকানার পক্ষে কাগজাদি থাকা লাগে। ভায়া দলিল না থাকলে রেজিস্টার অফিস হতে সংগ্রহ করুন।")
        elif ('আরেকদাগ' in Input or 'দাগ' in Input) and ('নামজারি' in Input):
            dispatcher.utter_message(text = "রেজিস্টার্ড দলিলে যে দাগ থাকে সে দাগে নামজারি হবে, অন্য দাগে হবে না।")
        elif 'মামলা' in Input and 'নামজারি' in Input:
            dispatcher.utter_message(text = "সহকারি কমিশনার ভূমি কোন জমি নিয়ে দেওয়ানি মামলা বা আপিল মামলা থাকলে চূড়ান্ত রায় ও ডিক্রি না হলে নামজারি মঞ্জুর করবেন না।")
        elif ('নামজারির' in Input or 'নামজারি' in Input) and ('দখলে' in Input or 'দখল' in Input):
            dispatcher.utter_message(text = "নামজারির অনলাইন আবেদনে জমিদখলের তথ্য দিতে হয়। নামজারির জন্য কাগজাদির প্রমান জরূরি। জমির দখল জরুরি না, তবে সহকারি কমিশনার ভূমি নামজারির পক্ষের কাগজাদি দেখে এবং প্রয়োজনে পক্ষদের শুনে সিদ্ধান্ত দিবেন।")
        elif 'জমি আমার দখলে নাই কিন্তু আমার সব কাগজ আমার কাছে আছে খারিজ করা যাবে কিনা' in Input:
            dispatcher.utter_message(text = "নামজারির অনলাইন আবেদনে জমিদখলের তথ্য দিতে হয়। নামজারির জন্য কাগজাদির প্রমান জরূরি। জমির দখল জরুরি না, তবে সহকারি কমিশনার ভূমি নামজারির পক্ষের কাগজাদি দেখে এবং প্রয়োজনে পক্ষদের শুনে সিদ্ধান্ত দিবেন।")
        else:
            dispatcher.utter_message(response = "utter_Namzari_Information")


        return []

class OnlineKhotianNamjari(Action):
    """action_Online_KhotianANDNamjari"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Online_KhotianANDNamjari"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_Online_KhotianANDNamjari")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if 'কি কাজে' in Input and ('আসে' in Input or 'লাগে' in Input or 'আসবে' in Input or 'লাগবে' in Input or 'ব্যাবহার' in Input):
            dispatcher.utter_messgae(text = "খতিয়ান, পর্চা থাকা মানে আপনার জমির মালিকান নিশ্চিত, জমির হিসাব সঠিক, খাজনা, ভূমি উন্নয়ন কর দিয়ে মালিকানার ধারাবাহিকতা রক্ষা, দখল নিশ্চিত করা, জমি ভালবাবে ব্যবহারের পরিকল্পনা করা যায়। অনলাইনে খতিয়ান, পর্চা থাকলে আপনার হারানোর ভয় থাকবে না, যখন প্রেয়োজন আপনি নিয়ে ব্যবহার করতে পারবেন।")
        elif 'অনলাইনে' in Input and 'ডাউনলোড' in Input and ('করা যায় না' in Input or 'করা যাচ্ছে না' in Input):
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, এরপর সাপোর্ট টিকেট অপশন সিলেক্ট করে সংশ্লিষ্ট সমবিস্তারিত উল্লেখ করে একটি সাপোর্ট টিকেট প্রস্তুত করতে হবে। সমবিস্তারিত তে অবশ্যই জেলা, উপজেলা, মৌজা ও খতিয়ান বা পর্চা নম্বর উল্লেখ করতে হবে। সাপোর্ট টিম আপনার প্রদত্ত ইমেইল এড্রেস, ফোন নম্বরে আপনাকে যথোপযুক্ত উত্তর প্রদান করবে।")
        elif 'খতিয়ান পাওয়া যায় না' in Input and ('অনলাইনে' in Input or 'অনলাইন' in Input):
            dispatcher.utter_message(text = "খতিয়ান,পর্চা আপলোড থাকলে পাবেন। ইউনিয়ন ভূমি অফিস বা উপজেলা ভূমি অফিসে জানুন যে, আপনার মৌজার খতিয়ান, পর্চা আপলোড করা হয়েছে কিনা")
        elif 'মালিকানা' in Input or 'যাচাই' in Input or 'দাগ নাম্বার' in Input:
            dispatcher.utter_message(text = "আপনি আপনার জমির খতিয়ান, পর্চা  কিংবা দাগ নাম্বার দিয়ে অনলাইন ই পর্চায় সার্চ করুন। খতিয়ান, পর্চার দাগ নাম্বার জানা না থাকলে জমির মালিক বা তার পিতার নাম দিয়ে সার্চ করেও আপনার জমি দেখতে পারবেন।")
        elif 'না পাওয়া' in Input and 'দাগ নম্বর' in Input:
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, এরপর সাপোর্ট টিকেট অপশন সিলেক্ট করে সংশ্লিষ্ট সমবিস্তারিত উল্লেখ করে একটি সাপোর্ট টিকেট প্রস্তুত করতে হবে। সমবিস্তারিত তে অবশ্যই জেলা, উপজেলা, মৌজা ও খতিয়ান বা পর্চা নম্বর উল্লেখ করতে হবে। সাপোর্ট টিম আপনার প্রদত্ত ইমেইল এড্রেস, ফোন নম্বরে আপনাকে যথোপযুক্ত উত্তর প্রদান করবে।")
        elif 'দাগসূচী' in Input or 'দাগসূচীর' in Input or 'দাগ সূচীর' in Input or 'দাগ সুচির' in Input:
            dispatcher.utter_message(text = "সি এস বা আর এস দাগের বিপরিতে বি আর এস দাগ সূচি পাওয়ার সরকার নির্ধারিত অনলাইনে ফি কত সেই সম্পর্কে তথ্য জানানোর সুযোগ নেই, ভূমি অফিস থেকে জানতে পারবেন।")
        elif 'অনলাইনে নামজারি খতিয়ান কি করে পাবো' in Input or 'অনলাইনে নামজারি পর্চা কি করে পাবো' in Input:
            dispatcher.utter_message(text="পূর্বের কোন ম্যানুয়াল কোন নামজারি কেসের অনলাইন পর্চা/খতিয়ান সংগ্রহ করতে হয় তবে  ইপরছা ডট গভ তে গিয়ে নামজারি খতিয়ান বাটনে ক্লিক করে তথ্য দিয়ে সংগ্রহ করতে হবে।নামজারি খতিয়ান অনলাইনে পাওয়া যাবে যদি তা অনলাইনে আপলোড থাকে। অন্যথায় জেলা রেকর্ড রুমে আবেদন করে সংগ্রহ করতে হবে।")
        else:
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, এখানে সার্ভে খতিয়াান ও নামজারি খতিয়ান অপশনের মধ্যে, আপনার প্রয়োজন অনুযায়ি সঠিক বাঁটোনে ক্লিক করুন, এর পরে খতিয়ান অনুসন্ধান টেবিলের সঠিক বিভাগ, জেলা,উপজেলা, মৌজা বাছাই করলে আপনার তথ্য দেখতে পাবেন।")


        return []

class holdingNumber(Action):
    """action_HoldingNumber"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_HoldingNumber"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        if 'বাড়ির' in Input and 'হোল্ডিং নাম্বার' in Input and 'কিভাবে' in Input:
            dispatcher.utter_message(text = "হোল্ডিং নম্বর পেতে হলে আপনাকে সিটি কর্পোরেশনে, পৌরসভায় যেতে হবে। বাড়ির জমির মালিক হিসাবে জরীপে রেকর্ডীয় মালিক হলে বা নামজারি সূত্রে মালিক হলে ইউনিয়ন ভূমি অফিসে মালিকের নামে জমির জন্য হোল্ডিং খোলা হয়। এছাড়া, আপনি এল ডি ট্যাক্স ডট গব ডট বিডি, তে গিয়ে অনলাইনে খাজনা দিয়ে হোল্ডিং নম্বর জানতে পারবেন।")
        elif ('হোল্ডিং নাম্বার দিচ্ছে না' in Input or 'অনলাইনে হোল্ডিং নাম্বার দিচ্ছে না' in Input) and ('আপলোড করা হয়েছে' in Input or 'পরিশোধ করা হয়েছে' in Input or 'আবেদন' in Input):
            dispatcher.utter_message(text = "অনুগ্রহ করে আপনি ইউনিয়ন ভূমি অফিসে যোগাযোগ করবেন। কেননা হোল্ডিং এর তথ্য আপলোডের এখতিয়ারটি শুধুমাত্র ইউনিয়ন ভূমি অফিসের রয়েছে।")
        elif 'হোল্ডিং নাম্বারটা কিভাবে পাব' in Input:
            dispatcher.utter_message(text = "হোল্ডিং নম্বরটি সংশ্লিষ্ট ইউনিয়ন ভূমি অফিস থেকে দেওয়া হয়ে থাকে। অনুগ্রহ করে আপনি ইউনিয়ন ভূমি অফিসে যোগাযোগ করবেন।")
        elif 'সময়' in Input and 'হোল্ডিং' in Input:
            dispatcher.utter_message(text = "খতিয়ান, পর্চা আপলোড করার তিন কর্মদিবসের মধ্যে আপনি হোল্ডিং পাবেন।")
        else:
            dispatcher.utter_message(text = "অনুগ্রহ করে আপনি ইউনিয়ন ভূমি অফিসে যোগাযোগ করবেন। কেননা হোল্ডিং এর তথ্য আপলোডের এখতিয়ারটি শুধুমাত্র ইউনিয়ন ভূমি অফিসের রয়েছে।")


        return []

class ApplyNamzari(Action):
    """action_NamzariApplication"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_NamzariApplication"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if ('পক্ষে' in Input or 'আত্মীয়' in Input or 'অন্যকেউ' in Input or 'অন্য কেউ' in Input or 'আত্মীয়কে' in Input or 'ভাই' in Input) and ('আবেদন' in Input or 'নামজারি' in Input):
            dispatcher.utter_message(text = "জি করতে পারে। সেক্ষেত্রে আবেদন ফর্ম পূরণের সময় আবেদনকারীর প্রতিনিধির ও আবেদনকারীর প্রত্যেকের এক কপি পা্সপোর্ট সাইজের ছবি, নিজ নিজ স্বাক্ষর, জাতীয় পরিচয় পত্র, পা্সপোর্ট, জন্ম নিবন্ধ সনদ এবং যাহা প্রযোজ্য, সংযুক্ত করে দিতে হবে।")
        elif 'প্রবাসীরা' in Input or 'বাহিরে থাকি' in Input or 'দেশের বাহিরে থাকি' in Input or 'বিদেশ' in Input or 'প্রবাসীরা' in Input or 'প্রবাস' in Input or 'বিদেশী' in Input or 'বিদেশে' in Input:
            dispatcher.utter_message(text = "প্রবাসিদের বিদেশ থেকে নামজারির জন্য প্রথমে অনলাইনে নামজারি আবেদন এবং ফী পরিশোধ করবেন। অনলাইনে শুনানীর মাধ্যমে নামজারি কার্যক্রম সম্পাদন করতে পারবেন।")
        else:
            dispatcher.utter_message(response = "utter_ApplyNamzari")


        return []

class ApplyNamzariCancel(Action):
    """action_NamzariCancel"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_NamzariCancel"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        #dispatcher.utter_message(text = "কারো নামে নামজারীর আদেশের ত্রিশ দিনের মধ্যে উপযুক্ত কারণ থাকলে সহকারি কমিশনার এর  নিকট ঐ নামজারী আদেশ বাতিলের জন্য  রিভিউ, মিস কেস মামলা দায়ের করতে হয়। অথবা ত্রিশ দিনের মধ্যে অতিরিক্ত জেলা প্রশাসক, রাজস্ব, এর  নিকট ঐ নামজারী আদেশ বাতিল, সংশোধন জন্য  আপিল কেস বা মামলা দায়ের করতে হয়।")




        if (("কি কারণে" in Input or "কারণে" in Input or "কারণ" in Input) and ('আবেদন বাতিল' in Input)) or 'আদেশে না' in Input:
            dispatcher.utter_message(text = "ভূমি কমিশনার সুনির্দিষ্ট কারণেই নামজারি আবেদন বাতিল বা নামঞ্জুর করেন এবং তা ই-নামজারি সিস্টেমে লিপিবদ্ধ করেন। নামজারি কোনো আবেদন বাতিল বা নামঞ্জুর হলে আবেদনের বিপরীতে আদেশটি অনলাইনেই দেখা যাবে। এজন্য ভূমি অফিসের কারো কাছে যাওয়ার প্রয়োজন হবে না।")
        else:
            if('আবেদন করি নাই' in Input):
                dispatcher.utter_message(text = "অন লাইনে খারিজের আবেদন করা যায়। এজন্য আপনি সকল প্রয়োজনীয় কাগজাদি স্ক্যান কপি সহ , ল্যান্ড ডট গভ ডট বিডি তে গিয়ে নামখারিজের ট্যাবে ক্লিক করুন, ও ধাপ গুলি অনুসরণ করুন।")
            else:
                dispatcher.utter_message(text = "নামজারী বাতিলের জন্য উক্ত নামজারীর আদেশের ত্রিশ দিনের মধ্যে কাগজপত্রসহ উপযুক্ত কারণ বর্ণনা করে উপজেলা ভূমি অফিসে মামলা দায়ের করার মাধ্যমে নামজারী বাতিল করা যায়")


        return []

class NamzariTime(Action):
    """action_NamzariTime"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_NamzariTime"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        dispatcher.utter_message(text = "সাধারণ ক্ষেত্রে আটাশ কার্য দিবস। প্রবাসীদের জন্য নয় থেকে বারো কার্য দিবস। মুক্তিযোদ্ধাদের জন্য দশ এবং শিল্প প্রতিষ্ঠানের জন্য সাত কার্য দিবস লাগবে। আমি আর কিভাবে আপনাকে সাহায্য করতে পারি")


        return []

class NamzariFee(Action):
    """action_NamzariFee"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_NamzariFee"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        if 'পর্চা নিতে ভূমি অফিসে কোন টাকা' in Input or 'খতিয়ান নিতে ভূমি অফিসে কোন টাকা' in Input or 'অনলাইনে খতিয়ান নিতে ভূমি অফিসে' in Input or 'পর্চা' in Input or 'খতিয়ান' in Input or 'পোস্ট' in Input:
            dispatcher.utter_message(text = 'অনলাইনে সার্টিফাইড খতিয়ান বা পর্চার ফি একশত টাকা মাত্র। এই ফি মোবাইল অ্যাপ্লিকেশান যেমন বিকাশ বা রকেট বা নগদ এর মাধ্যমে পরিশোধ করা যায় , ভূমি অফিসে কোনো টাকা দেয়ার প্রয়োজন হয় না,')
        elif 'নকশা ' in Input or 'মৌজা' in Input or 'ম্যাপ' in Input:
            dispatcher.utter_message(text = 'অনলাইনে নকশা ফি একশত টাকা লাগে , এই ফি মোবাইল অ্যাপ্লিকেশান যেমন বিকাশ, রকেট, নগদ এর মাধ্যমে পরিশোধ করা যায় , ভূমি অফিসে কোনো টাকা দেয়ার প্রয়োজন হয় না।')
        else:
            dispatcher.utter_message(text = "নামজারী করতে সর্বমোট এক হাজার একশত সত্তর টাকা লাগে। ই-মিউটেশনের আবেদনের সাথে, কোর্টফি ও নোটিশ জারি ফি বাবদ সত্তর টাকা, এবং নামজারি অনুমোদনের পর বাকি, এগারোশো টাকা পরিশোধ করতে হয়। সকল ফি অনলাইনে পরিশোধ করতে হবে। আমি আর কিভাবে আপনাকে সাহায্য করতে পারি ")

        return []

class CertifiedKhotian(Action):
    """action_CertifiedKhotian"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_CertifiedKhotian"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_CertifiedKhotian")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        
        if 'সার্টিফাইড কপি কি' in Input or ('সার্টিফাইড কপি' in Input or 'ভবিষ্যতে কোন কাজ করা যাবে' in Input):
            dispatcher.utter_message(text= "সার্টিফাইড কপি হল সত্যায়িত অবিকল কপি। সার্টিফাইড দ্বারা মূল কাগজের মত কপির মাধ্যমে আপনি যে কোন বিষয় সম্পাদন করতে পারবেন।")
        elif 'অনলাইন নামজারী খতিয়ানের সার্টিফাই কপি' in Input:
            dispatcher.utter_message(text = "এক্ষেত্রে বর্তমান অনলাইন নামজারী খতিয়ানের সার্টিফাই কপি হয়।")
        else:
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, নাগরিক কর্নার অপশনে গিয়ে, আবেদনের অবস্থা বাটনে  ক্লিক করে পেজে গিয়ে আবেদনের রেফারেন্স নম্বর দিয়ে ট্রাক করলে আবেদনের অবস্থা জানতে পারবেন।")


        return []

class ActionLandMaps(Action):
    """action_LandMaps"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_LandMaps"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_LandMaps")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        if ('পারসেল' in Input or 'চিটা' in Input or 'হাত' in Input) and ('ম্যাপ ' in Input or 'নক্সা' in Input):
            dispatcher.utter_message(text= "অনলাইন এর মাধ্যমে পারসেল, চিটা, হাত নক্সা ম্যাপ বের করার কোন সুযোগ নেই।")
        elif 'পেতে কতদিন লাগবে' in Input or 'কতদিন লাগবে' in Input:
            dispatcher.utter_message(text = "এক্ষেত্রে আবেদনের প্রেক্ষিতে আপনাকে ডেলিভারি ডেট দেয়া হবে, এবং আপনি ডাকযোগে নিজ ঠিকানায় ডেলিভারি নিতে পারেন অথবা অফিস কাউন্টার থেকে সংগ্রহ করতে পারেন।")
        elif 'খুঁজে পাচ্ছি না' in Input:
            dispatcher.utter_message(text = "পর্যায়ক্রমে আপলোডের কাজ চলছে। অনুগ্রহ করে অপেক্ষা করুন।")
        elif ('প্রিন্ট কপি' in Input or 'স্ক্যান কপি' in Input) and ('ভালো' in Input or 'ভাল' in Input):
            dispatcher.utter_message(text = "এক্ষেত্রে দুটোই ব্যাবহার করা যায়।")
        elif 'অরিজিনাল' in Input or 'ফটোকপি' in Input or 'ম্যাপ টা অরিজিনাল টা নাকি ফটোকপি' in Input:
            dispatcher.utter_message(text = "এক্ষেত্রে আপনাকে মৌজা এর সার্টিফাইড কপি দেয়া হবে।")
        else:
            dispatcher.utter_message(text = "মৌজা ম্যাপটি পেতে আপনাকে অনলাইনে আবেদন করতে হবে। আবেদনটি আপনি ই পরচা ডট গব ডট বিডি, এই ওয়েবসাইটে প্রবেশ করে পেতে পারেন।")


        return []

class ActionKhotian_Appication(Action):
    """action_Khotian_Appication"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Khotian_Appication"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_Khotian_Appication")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        if 'খতিয়ান' in Input and 'চেক' in Input:
            dispatcher.utter_message(text = "অনুগ্রহপূর্বক ই পরচা ডট গব ডট বিডি, এই ওয়েবসাইট এ প্রবেশ করুন। এরপর নাগরিক কর্নার থেকে খতিয়ান, পর্চা  আবেদন অপশনটি নির্বাচন করে খতিয়ান,পর্চা অনলাইন আবেদন ফরম এ গিয়ে ফরমের যাবতীয় তথ্যাদি দিয়ে অনুসন্ধানের মাধ্যমে সার্টিফাইড কপিটি সংগ্রহের মাধ্যমে উক্ত বিষয়টি সম্পর্কে জানতে পারবেন।")
        else:
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, নাগরিক কর্নার অপশনে গিয়ে, খতিয়ান অনুসন্ধান ক্লিক করে খতিয়ান তথ্য দিয়ে ক্লিক করলে একটি ফরম আসবে।")


        return []


class TotalLand(Action):
    """action_TotalLand"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_TotalLand"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_TotalLand")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        dispatcher.utter_message(respones = "utter_landIhave")


        return []

class LandTaxProcess(Action):
    """action_Land_TaxProcess"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Land_TaxProcess"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_Land_TaxProcess")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if ('বিদেশে' in Input or 'বিদেশ' in Input) and ('কর' in Input or 'ট্যাক্স' in Input):
            dispatcher.utter_message(text = "আপনার  বাংলাদেশের এনআইডি থাকলে পরেবেন। এল ডি ট্যাক্স ডট গব ডট বিডি, এই ওয়েব সাইটে প্রবেশ করে ভূমি উন্নয়ন কর নাগরিক নিবন্ধন করুন। এসএমএস এর মাধ্যমে হোল্ডিং নম্বর পাবেন। একই সাইটের নাগরিক প্রোফাইলে হোল্ডিং এর বিস্তারিত অপশন থেকে তথ্য যাঁচাই করতে পারবেন।হোল্ডিং এর বিস্তারিত অপশনে থাকা অনলাইন পেমেন্ট অপশনে পেমেন্ট গেইট ওয়ে বেছে নিন বা ইন্টারনেট ব্যাংকিং বেছে নিন। বাছাইকৃত পেমেন্ট গেইটওয়ে থেকে ভূমি উন্নয়ন করের দাবি পরিশোধ করুন। সরাসরি ব্যাংকেও ভূমি উন্নয়ন করা জমা দেয়া যাবে। ভূমি উন্নয়ন করা জমা হয়ে গেলে আপনার নাগরিক নিবন্ধনে আপনার দাখিলা পাবেন।")
            return []
        elif 'অনলাইনে ভূমি উন্নয়ন কর' in Input and ('কর মওকুফ' in Input or 'মওকুফ' in Input or 'মাফ'in Input or 'কর মাফ' in Input):
            dispatcher.utter_message(text = "অনলাইনে পেমেন্ট করলে ভূমি উন্নয়ন কর মওকুফ হয় না। ভূমি কর মওকুফ হয় যদি কারো পরিবারের মোট কৃষি জমি পঁচিশ বিঘার কম থাকে।কোন অকৃষি জমির খাজনা বা ভূমি উন্নয়ন কর  বা ভূমি উন্নয়ন কর মওকফ হয় না।")
            return []
        elif 'খতিয়ান' in Input and 'অনলাইন কপি' in Input and 'কর দেওয়া' in Input:
            dispatcher.utter_message(text = "খতিয়ান এর অনলাইন কপি দিয়ে ভূমি উন্নয়ন কর দেওয়া যাবে।")
            return []
        elif ('উত্তরাধিকার' in Input or 'ওয়ারিশ' in Input) and ('খাজনা' in Input or 'উন্নয়ন কর' in Input):
            dispatcher.utter_message(text = "উত্তরাধিকার সূত্রে অনলাইনে খাজনা দেওয়ার সুযোগ আছে। এল ডি ট্যাক্স ডট গব ডট বিডি, এই ওয়েবসাইটের মাধ্যমে নিবন্ধন করুন। খতিয়ানের অপশনে উত্তরাধিকার অপশনটি সিলেক্ট করে খতিয়ানের তথ্য আপলোড করুন। এরপর ভূমি উন্নয়ন কর অনলাইন পেমেন্ট করে দিন, পেমেন্ট এর পর নাগরিক নিবন্ধনে আপনার দাখিলা পাবেন।")
            return []
        elif ('মুখস্থ' in Input or 'মওকুফ' in Input or 'খাজনা মুখোশ' in Input or 'মাফ' in Input):
            dispatcher.utter_message(text = "যে কোনো পরিবারের মোট কৃষি জমি পঁচিশ বিঘা বা তার কম হলে কর দিতে হবে না, তবে দশ টাকা দিয়ে মওকুফ দাখিলা অন লাইনেও নিতে পারেন, কর দিতে প্রবেশ করুন ল্যান্ড ডট গভ ডট বিডি বা সরাসরি ব্যংকে গিয়ে দিতে পারেন।")
            return []
        else:
            dispatcher.utter_message(text = "আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, নাগরিক কর্নার অপশনে গিয়ে, খতিয়ান অনুসন্ধান ক্লিক করে খতিয়ান তথ্য দিয়ে ক্লিক করলে একটি ফরম আসবে।")
            return []

class LandTax(Action):
    """Action_Land_Tax"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_Land_Tax"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("Action_Land_Tax")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if 'দাখিলা' in Input:
            dispatcher.utter_message(text = "দাখিলা বা ফাইনাল রশিদটি আপনার নিবন্ধিত প্রোফাইলের দাখিলা অপশন থেকেই পেয়ে যাবেন। এক্ষেত্রে আপনাকে ভূমি অফিসে যাওয়ার প্রয়োজন নেই।")
        else:
            dispatcher.utter_message(response = "utter_LandTax_Registration")

        # if intentName == 'DigitalPayment':
        #     dispatcher.utter_message(response = "utter_DigitalPayment")
        # elif intentName == 'MobileNumberChanges':
        #     dispatcher.utter_message(response = "utter_AT")
        # elif intentName == 'LandTax_Registration':
        #     dispatcher.utter_message(response = "utter_LandTax_Registration")
        # else:
        #     return [UserUtteranceReverted()]

        return []

class DigitalPayment(Action):
    """action_Payment"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_Payment"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("action_Payment")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if ('ডিসিআরের' in Input or 'ডিসিআর' in Input or 'ডি সি আর' in Input) and 'পরিশোধ' in Input:
            dispatcher.utter_message(text = "ডিসিআর এর টাকা অনলাইনে পরিশোধ করা যাবে না, উপজেলা ভূমি অফিসে পরিশোধ করতে হবে।")
            # dispatcher.utter_message(text = "পেমেন্ট করার ক্ষেত্রে নগদে প্রবেশ করে বিল পে অপশনটি নির্বাচন করতে হবে। লাল চিহ্নিত সার্চ অপশনে গিয়ে ই-নামজারি অপশনটি নির্বাচন করতে হবে। এরপর পরবর্তী অপশন টি ক্লিক করতে হবে।")
        elif  'ডিসি আর ফি' in Input or 'ডিসি আর' in Input or 'ডিসিআর ফি কি অনলাইনে' in Input:
            dispatcher.utter_message(text = "আপনি যদি অনলাইনে নামজারির আবেদন করে থাকেন ডিসি আর পেমেন্টটি অনলাইনে পরিশোধ করতে পারবেন। আর যদি ম্যানুয়ালি করে থাকেন এবং উপজেলা ভূমি অফিস থেকে সংগ্রহ করতে পারবেন। অতিরিক্ত টাকা চাওয়া হয় আপনি চাইলে আমাদের কাছে অভিযোগ করতে পারেন।")

        dispatcher.utter_message(template = "utter_DigitalPayment")


        return []

class NamzariInformation(Action):
    """Action_Namzari_Information"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "Action_Namzari_Information"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        intentName = tracker.latest_message['intent'].get('name')

        print("Action_Namzari_Information")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if intentName == 'DigitalPayment':
            dispatcher.utter_message(response = "utter_DigitalPayment")
        elif intentName == 'ApplyNamzari':
            dispatcher.utter_message(response = "utter_ApplyNamzari")
        elif intentName == 'NamzariDocuments':
            dispatcher.utter_message(response = "utter_NamzariDocuments")
        else:
            return [UserUtteranceReverted()]

        return []

class ResetNamzariStatusInitials(Action):
    """action_reset_NamzariStatusInitials"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_NamzariStatusInitials"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("Reset Namzari_Status_Form related info.")

        return[
                SlotSet("ApplicationNumber", None),
                SlotSet("ApplicationNumber_confirm", None),
                SlotSet("APtext", None),
                SlotSet("DivisionName", None),
                SlotSet("Incomplete_Story", True),
            ]

class ActionValidationNamzari_status(FormValidationAction):
    """validate_Namzari_Status_Form"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_Namzari_Status_Form"

    async def validate_DivisionName(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        """Executes the action"""
        print("validate_DivisionName")
        Division_Is = tracker.get_slot("DivisionName")
        print("Division Name is: ", Division_Is)
        Division_List = ['Dhaka', 'Khulna', 'Rajshahi', 'Chittagong', 'Sylhet', 'Barisal', 'Rangpur', 'Mymensingh']
        if Division_Is not in Division_List:
            dispatcher.utter_message(response = "utter_Invalid_Division")
            return {"DivisionName": None, "requested_slot": "DivisionName"}
        print("Your Division Name is in the Division_List")
        return {}

    async def validate_ApplicationNumber(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print("validate_check_balance_form")
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])

        print("validate_ApplicationNumber")
        Application_Number = tracker.get_slot("ApplicationNumber")
        print(f"Application Id is : {Application_Number}")
        if int(Application_Number) < 100:
            dispatcher.utter_message(response = "utter_Invalid_ApplicationNumber")
            return {"ApplicationNumber": None, "requested_slot": "ApplicationNumber"}
        else:
            print(f"Your Application_Number is found and it is {Application_Number}.")
            app_num = Application_Number[-4:]
            print(f"Last 4 digit of the application number is {app_num}")
            APINword = numberTranslate(app_num)
            print(APINword)
            # return {"APtext": APINword, "requested_slot": "ApplicationNumber_confirm"}
            return {"Found" : True, "APtext": APINword}

    # async def validate_ApplicationNumber_confirm(
    #     self,
    #     slot_value: Any,
    #     dispatcher: CollectingDispatcher,
    #     tracker: Tracker,
    #     domain: Dict[Text, Any],
    # ) -> List[Dict]:
    #     """Executes the action"""
    #     print(tracker.latest_message['intent'].get('name'))
    #     print(tracker.latest_message['intent']['confidence'])
    #     app_confirm = tracker.get_slot("ApplicationNumber_confirm")

    #     intent = tracker.latest_message['intent'].get('name')

    #     if intent == "affirm":
    #         return{"Found" : True, "ApplicationNumber_confirm": "affirm", "APtext": None}

    #     elif intent == "deny":
    #         print("number is not correct.")
    #         return {"ApplicationNumber_confirm": None, "ApplicationNumber": None, "APtext": None, "requested_slot": "ApplicationNumber"}
    #     else:
    #         print("something else.")
    #         return {"ApplicationNumber_confirm": None, "requested_slot": "ApplicationNumber_confirm"}

class Action_NamzariStatusResponse(Action):
    """action__NamzariStatus_Response"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action__NamzariStatus_Response"


    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        """Executes the action"""

        #aid=['6920352']
        found = tracker.get_slot("Found")
        division_name = tracker.get_slot("DivisionName")
        aid = tracker.get_slot("ApplicationNumber")
        division='3'

        # "description": "1 = Barisal; 2 = Chittagong; 3 = Dhaka; 4 = Khulna; 5 = Rajshahi; 6 = Rangpur; 7 = Sylhet; 8 = mymensingh;",
        if(division_name=='Dhaka'):
           division='3'
        if(division_name=='Barisal'):
           division='1'
        if(division_name=='Chittagong'):
           division='2'
        if(division_name=='Khulna'):
           division='4'
        if(division_name=='Rajshahi'):
           division='5'
        if(division_name=='Rangpur'):
           division='6'
        if(division_name=='Sylhet'):
           division='7'
        if(division_name=='Mymensingh'):
           division='8'

        res="আপনার আবেদনটি উপজেলা ভূমি অফিসে জমা হয়েছে।"

        try:

            url = "https://trapi7.land.gov.bd/api/getToken"

            payload = {'username': 'gplex_land','password': ')#lr.i#@#land#','clientid': 'gplex'}
            headers = {
                'content-type': "application/x-www-form-urlencoded",
                'cache-control': "no-cache"
                }

            response = requests.request("POST", url, data=payload, headers=headers)

            jdata = json.loads(response.text)
            print(jdata)



            url = "https://api.land.gov.bd/api/get-application-state"

            payload={'division_id': str(division),'application_id': str(aid)}
            print("PAYLOAD")
            print(payload)
            headers = {
                'apiauthorization': "bearer "+jdata['token'],
                'cache-control': "no-cache",
                'content-type': "application/x-www-form-urlencoded"
                }

            response = requests.request("POST", url, data=payload, headers=headers)

            jdata = json.loads(response.text)
            print(jdata)
        except:
            print("Error: API Exception.")
        finally:
             res="আপনার আবেদনটি উপজেলা ভূমি অফিসে জমা হয়েছে।"

        res="আপনার আবেদনটি উপজেলা ভূমি অফিসে জমা হয়েছে।"
        if(jdata['response']=='success'):
            found = True
            if(jdata['data']['application_current_status']=='শুনানির জন্য আদেশ'):
                numeric_words
                date=re.findall(r'\(.*?\)', jdata['data']['to_be_done'])
                dst=' '
                if(len(date)>0):
                    ds=date[0][1:-1]
                    dsa=ds.split('/')

                    for x in dsa:
                        for k, v in numeric_words.items():
                            if(x==k):
                                dst=dst+' , '+str(v)
                res="আপনার আবেদনটির শুনানির দিন "+str(dst)+" তারিখে ধার্য করা হয়েছে।"
                print(res)

            if(jdata['data']['application_current_status']=='খতিয়ান প্রস্তুত'):
                res="আপনার আবেদনের খতিয়ানটি প্রস্তুত হয়ে গেছে, নামজারি পোর্টালে গিয়ে এক হাজার একশো টাকা ডিসিআর ফি পরিশোধ করে খতিয়ান সংগ্রহ করুন"

            if(jdata['data']['application_current_status']=='আবেদন নামঞ্জুর হিসাবে গন্য'):
                res="আপনার আবেদনটি নামঞ্জুর হিসাবে গন্য করা হয়েছে।"


        dispatcher.utter_message(text = res)
        # if found:
        #     dispatcher.utter_message(text = res)
        # else:
        #     dispatcher.utter_message(text = "এই আবেদন সংক্রান্ত কোন তথ্য আমাদের ডাটাবেইজ এ পাওয়া যায় নাই। তাই আপনার কলটি একজন এজেন্টের কাছে ট্রান্সফার করা হচ্ছে, একটু অপেক্ষা করুন।")
        return [
            SlotSet("DivisionName", None),
            SlotSet("ApplicationNumber", None),
            SlotSet("ApplicationNumber_confirm", None),
            SlotSet("Incomplete_Story", False),
            SlotSet("Found", False),
            ]


class ResetCommon_FormInitials(Action):
    """action_reset_ComplainInfo_Initials"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_ComplainInfo_Initials"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("Reset Complain_Form related info.")

        return[
                SlotSet("ApplicationNumber", None),
                SlotSet("DivisionName", None),
                SlotSet("NID_Number", None),
                SlotSet("Incomplete_Story", False),
            ]


class ActionValidationCommonForm(FormValidationAction):
    """validate_Common_Form"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_Common_Form"

    async def validate_DivisionName(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        """Executes the action"""
        print("validate_DivisionName")
        Division_Is = tracker.get_slot("DivisionName")
        print("Division Name is: ", Division_Is)
        Division_List = ['Dhaka', 'Khulna', 'Rajshahi', 'Chittagong', 'Sylhet', 'Barisal', 'Rangpur', 'Mymensingh']
        if Division_Is not in Division_List:
            dispatcher.utter_message(response = "utter_Invalid_Division")
            return {"DivisionName": None, "requested_slot": "DivisionName"}
        print("Your Division Name is in the Division_List")
        return {}

    async def validate_ApplicationNumber(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])

        print("validate_ApplicationNumber")
        Application_Number = tracker.get_slot("ApplicationNumber")
        print(f"Application Id is : {Application_Number}")
        if int(Application_Number) < 100:
            dispatcher.utter_message(response = "utter_Invalid_ApplicationNumber")
            return {"ApplicationNumber": None, "requested_slot": "ApplicationNumber"}
        else:
            print("Your Application_Number is found.")
            return {}

    async def validate_NID_Number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])

        print("validate_NID_Number")
        NID = tracker.get_slot("NID_Number")
        print(f"National Id is : {NID}")
        if len(NID) not in range(10, 18):
            dispatcher.utter_message(response = "utter_Invalid_NID_Number")
            return {"NID_Number": None, "requested_slot": "NID_Number"}
        else:
            print("Your NID_Number is found.")
            return {"requested_slot": None}

class Action_CommonForm_Response(Action):
    """action_CommonForm_Response"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_CommonForm_Response"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:

        """Executes the action"""
        dispatcher.utter_message(text = "আপনার অভিযোগটি গ্রহণ করা হয়েছে, আপনার সাথে শীঘ্রয় আমাদের থেকে যোগাযোগ করা হবে। আর আপনি একটি লিখিত অভিযোগ উপজেলা ভূমি অফিসে করে রাখুন।")
        return [
            SlotSet("DivisionName", None),
            SlotSet("ApplicationNumber", None),
            SlotSet("Incomplete_Story", False),
            ]


class Action_AssetsAS_inheritor(Action):
    """action_AssetsAS_inheritor_response"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_AssetsAS_inheritor_response"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("action_AssetsAS_inheritor_response")
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        if 'খারিজ' in Input or 'নামজারি' in Input:
            dispatcher.utter_message(text = "ওয়ারিশানসুত্রে জমি খারিজের জন্য সহঅংশীদার থাকলে বন্টননামা দিতে হবে। বন্টননামা রেজিস্টার্ড বা আদালতের আদেশ মোতাবেক হতে পারে।")
        elif 'কোথায়' in Input or 'পাবো' in Input:
            dispatcher.utter_message(text = "বন্টননামা বা উত্তরাধিকার সনদ ইউনিয়ন পরিষদ থেকে নিতে হবে। বন্টননামা বা উত্তরাধিকার সনদ ছাড়া জমি নামজারি হবে না।")
        else:
            dispatcher.utter_message(response = "utter_ask_rephrase")


        return[]
#################################################################################################################################################################################
#########################################################------------ভূমি মন্ত্রণালয়------------#####################################################################################
#################################################################################################################################################################################

class JoriperNokshaMapCSSSRSBRS(Action):
    """action_TotalLand"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_JoriperNokshaMapCSSSRSBRS"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print("action_JoriperNokshaMapCSSSRSBRS")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")
        dispatcher.utter_message(template= "utter_JoriperNokshaMapCSSSRSBRS")
        print(dispatcher.messages)

        return []

class NokshaApplicationState(Action):

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_nokshaApplicationState"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print("action_nokshaApplicationState")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if('খতিয়ানের' in Input or 'খতিয়ান' in Input or 'পর্চার' in Input or 'পর্চা' in Input):
            dispatcher.utter_message(text="আপনি ই পরচা ডট গব ডট বিডি ভিজিট করুন, নাগরিক কর্নার অপশনে গিয়ে, আবেদনের অবস্থা বাটনে  ক্লিক করে পেজে গিয়ে আবেদনের রেফারেন্স নম্বর দিয়ে ট্রাক করলে আবেদনের অবস্থা জানতে পারবেন।")
        else:
            dispatcher.utter_message(template= "utter_NokshaApplicationState")
        print(dispatcher.messages)

        return []


class NokshaORmapFee(Action):
    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_nokshaORmapFee"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        dispatcher.utter_message(text="অনলাইনে নকশা ফি একশত টাকা লাগে , এই ফি মোবাইল অ্যাপ্লিকেশান যেমন বিকাশ, রকেট, নগদ এর মাধ্যমে পরিশোধ করা যায় , ভূমি অফিসে কোনো টাকা দেয়ার প্রয়োজন হয় না।")
        #dispatcher.utter_message(template="utter_NokshaORmapFee")
        print(dispatcher.messages)

        return []

# class OnlineNokshaORmapStatusCheck(Action):
#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_onlineNokshaORmapStatusCheck"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         dispatcher.utter_message(template="utter_onlineNokshaORmapStatusCheck")
#         print(dispatcher.messages)


#         return []



class WhyShouldIPayLandTax(Action):
    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_WhyShouldIPayLandTax"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        dispatcher.utter_message(text="আপনার জমির পরিমান যত সামান্য হোক, ভূমি উন্নয়ন কর প্রতিবছর পরিশোধ করতে হবে, ভূমি উন্নয়ন কর না দিলে, জমি খাস হবে না , কোনো জমির ভূমি উন্নয়ন কর পরপর তিন বছর না দিলে সার্টিফিকেট মামলা দায়ের করে ভূমি উন্নয়ন কর বা খাজনা আদায় করা হয়")
        print(dispatcher.messages)

        return []


class DoIneedNamjarii(Action):
    """action_doIneedNamjari"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_doIneedNamjari"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print("action_doIneedNamjari")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")


        if 'আংশিক খাস  ব্যক্তির অংশের'in Input or 'আংশিক অর্পিত ব্যক্তির অংশের' in Input:
            dispatcher.utter_message(text = "সাধারণত হাল বা সাবেক যে কোন রেকর্ডে বা ভূমি অফিসের রেজিস্টারে খাস/অর্পিত থাকলে সে জমি কেনার প্রয়োজন নাই। নামজারির আবেদন করলে তদন্তরিপোর্টে  ইউনিয়ন ভূমি সহকারি অফিসার সুপারিশ করবেন না  বা সহকারি কমিশনার ভূমি শুনানিকালে কাগজাদি দেখে সরকারি স্বার্থ থাকলে নামজারির অনুমোদন দিবেন না।")
        elif 'হাল রেকর্ডে ব্যক্তির নামে তার কাছ থেকে কিনেছি কিন্ত সাবেক রেকর্ডে খাস' in Input or 'অর্পিত জমি কিনলে নামজারি হয় কিনা' in Input or 'খাস জমি কিনলে নামজারি হয় কিনা' in Input:
            dispatcher.utter_message(text = "সাধারণত হাল বা সাবেক যে কোন রেকর্ডে বা ভূমি অফিসের রেজিস্টারে খাস/অর্পিত থাকলে সে জমি কেনার প্রয়োজন নাই। নামজারির আবেদন করলে তদন্তরিপোর্টে  ইউনিয়ন ভূমি সহকারি অফিসার সুপারিশ করবেন না  বা সহকারি কমিশনার ভূমি শুনানিকালে কাগজাদি দেখে সরকারি স্বার্থ থাকলে নামজারির অনুমোদন দিবেন না।")
        else:
            dispatcher.utter_message(template= "utter_action_doIneedNamjari")


        print(dispatcher.messages)

        return []


class KhajnaOfADeadPerson(Action):
    """action_KhajnaOfADeadPerson"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_KhajnaOfADeadPerson"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print("KhajnaOfADeadPerson")

        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if 'মৃত ব্যক্তির ওয়ারিশরা কি অনলাইনে ভূমি উন্নয়ন কর' in Input or 'মৃত ব্যক্তির উত্তরাধিকারীরা কি অনলাইনে ভূমি উন্নয়ন কর' in Input:
            dispatcher.utter_message(text = "মৃত ব্ব্যক্তির উত্তরাধিকার/ওয়াশিান নিজের নামে প্রোফাইল রেজিস্টার করে খতিয়ান/পর্চা  অপশনে উত্তরাধিকার নির্বাচন করার মাধ্যমে খাজনা/ভূমি উন্নয়ন কর  প্রদান করতে পারবেন।")
        elif 'মৃত ব্যক্তির ওয়ারিশরা কি অনলাইনে খাজনা' in Input or 'মৃত ব্যক্তির উত্তরাধিকারীরা কি অনলাইনেখাজনা' in Input:
            dispatcher.utter_message(text = "মৃত ব্ব্যক্তির উত্তরাধিকার/ওয়াশিান নিজের নামে প্রোফাইল রেজিস্টার করে খতিয়ান/পর্চা  অপশনে উত্তরাধিকার নির্বাচন করার মাধ্যমে খাজনা/ভূমি উন্নয়ন কর  প্রদান করতে পারবেন।")
        elif 'নামজারি করা নাই, মৃত মালিকের ওয়ারিশরা কিভাবে খাজনা' in Input:
            dispatcher.utter_message(text = "সাধারণত হাল বা সাবেক যে কোন রেকর্ডে বা ভূমি অফিসের রেজিস্টারে খাস/অর্পিত থাকলে সে জমি কেনার প্রয়োজন নাই। নামজারির আবেদন করলে তদন্তরিপোর্টে  ইউনিয়ন ভূমি সহকারি অফিসার সুপারিশ করবেন না  বা সহকারি কমিশনার ভূমি শুনানিকালে কাগজাদি দেখে সরকারি স্বার্থ থাকলে নামজারির অনুমোদন দিবেন না।")
        else:
            dispatcher.utter_message(template= "utter_KhajnaOfADeadPerson")
        print(dispatcher.messages)

class DoINeedToGoToLandOffice(Action):
    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_doIneedToGoLandOffice"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        dispatcher.utter_message(text="অনলাইনে ভূমি উন্নয়ন কর পরিশোধ করা যাবে।কাজেই ভূমি উন্নয়ন কর পরিশোধে ইউনিয়ন ভূমি অফিসে/সার্কেল ভূমি অফিসে/তহশিলে যাবা্র প্রয়োজন হবে না।আপনি ইচ্ছে করলে সরাসরি যে কোন ব্যাংকের যে কোন শাখায় গিয়ে ভূমি উন্নয়ন কর দিতে পারবেন")
        print(dispatcher.messages)

        return []


        action_taxOverThanTheUsual

class TaxOverThanTheUsual(Action):
    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_taxOverThanTheUsual"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        Input = tracker.latest_message.get('text')
        print(f"User Input was:{Input}")

        if('মওকুফ' in Input or 'মাফ' in Input):
            dispatcher.utter_message(text="যে কোন পরিবারের মোট কৃষি জমি পঁচিশ বিঘা বা তার কম হলে কর দিতে হবে না, তবে দশ টাকা দিয়ে মওকুফ দাখিলা অন লাইনেও নিতে পারেন, কর দিতে প্রবেশ করুন ল্যান্ড ডট গভ ডট বিডি বা সরাসরি ব্যংকে গিয়ে দিতে পারেন।")
        else:
            dispatcher.utter_message(text="সাধারণত সঠিক ভাবে  ভূমি উন্নয়ন কর ধার্য করা হয়। তারপরেও কোন আপত্তি থাকলে অনলাইনে ভূমি উন্নয়ন কর পরিশোধের ক্রম ধাপে হোল্ডিং ও ভূমি উন্নয়ন করের তথ্য ধাপে আপত্তি বাটনে ক্লিক করে আপনার আপত্তি প্রদান করবেন, আচ্ছা আবেদন করছিলাম এখন কপি পাচ্ছি না, আমি আর কিভাবে আপনাকে সহায়তা করতে পারি")
        print(dispatcher.messages)

        return []
