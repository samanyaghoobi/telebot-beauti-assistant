from datetime import datetime,timedelta
import logging
from telebot import TeleBot , custom_filters , types,apihelper
from telebot.storage import StateMemoryStorage
from telebot.types import InlineKeyboardButton ,InlineKeyboardMarkup,ReplyKeyboardMarkup,KeyboardButton,Message,CallbackQuery,ReplyKeyboardRemove
from auth.auth import *
from database.db_admin_list import *
from database.db_functions import delete_reservation, db_make_reserve_transaction
from database.db_weeklysetting import *
from database.db_create_table import *
from database.db_setwork import *
from database.db_users import *
from functions.custom_functions import  calculate_time_difference, extract_reserveId_and_userId, get_free_time_for_next_7day
from functions.log_functions import *
from functions.time_date import *
from messages.commands_msg import *
from messages.markups_text import *
from messages.messages_function import *
from states import *
from database.db_service import *
from functions.time_date import *
import re
##########################################################
bot =TeleBot(token = BOT_TOKEN, parse_mode="HTML")
bot_is_enable=True
##########################################################################################!  Admin Panel  
@bot.message_handler(commands=['admin'])
def start(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if not validation_admin (msg.from_user.id):
         bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
         return False
    markup=ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(mark_text_admin_empty_time,mark_text_admin_custom_reserve)
    markup.add(mark_text_admin_set_work_time , mark_text_admin_weekly_time)
    markup.add(mark_text_admin_set_service,mark_text_admin_bot_setting)
    markup.add(mark_text_admin_users_list,mark_text_admin_send_message_to_all)
    bot.send_message(chat_id=msg.from_user.id,text=text_user_is_admin, reply_markup=markup)
############################################################################################ markup mark_text_admin_custom_reserve
@bot.message_handler(func= lambda m:m.text == mark_text_admin_custom_reserve)
def bot_setting(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False 
    counter=0
    GenerateNext7Day()
    services=db_Service_Get_All_Services()
    if services is None or len(services) ==0:
        bot.send_message(chat_id=msg.from_user.id,text=text_no_service_available)
        return False
    sorted_serviceData_by_price = sorted(services, key=lambda item: item[3], reverse=True)
    services = sorted(sorted_serviceData_by_price, key=lambda item: item[4], reverse=True)
    services = [service + (0,) for service in services]
    markup=markup_generate_services_for_reserve(services,total_selected=counter,admin=True)

    text=text_reservation_init
    bot.send_message(chat_id=msg.chat.id,reply_markup=markup,text=text)

    bot.set_state(user_id=msg.chat.id,state=admin_State.state_reserve_custom_selecting,chat_id=msg.chat.id)


    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        data['services_choosing']=services
        data['services_name']=''
        data['counter']=counter
####selecting service - admin
@bot.callback_query_handler(func= lambda m:m.data.startswith("admin_select_service_"))
def convertUserID(call:CallbackQuery):
    service_id=(call.data.split("_"))[3]

    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services=data['services_choosing']
        services_name=str(data["services_name"])
        counter=data['counter']
    # change enable <=> disable
    for index, service in enumerate(services):

        if int(service[0]) == int(service_id):
            if service[5]==0: # if service need to active
                if counter== 0:# if basic info not set
                    services_name="خدمات انتخاب شده :"


                services[index]=service[:5] + (1,) 
                duration_time=convert_to_standard_time(f"{services[index][2]}")
                current_service_info=f"\n💅🏼 {services[index][1]} \n    💰 قیمت {services[index][3]} هزار تومان\n    ⏰ زمان موردنیاز {duration_time[:5]}"

                services_name=f"{services_name}\n {current_service_info}"
                counter=counter+1
            else:# if service wanna be disable
                services[index]=service[:5] + (0,) 
                duration_time=convert_to_standard_time(f"{services[index][2]}")
                current_service_info=f"\n💅🏼 {services[index][1]} \n    💰 قیمت {services[index][3]} هزار تومان\n    ⏰ زمان موردنیاز {duration_time[:5]}"
                services_name = services_name.replace(current_service_info, "").strip()
                counter=counter-1
            break
    markup=markup_generate_services_for_reserve(services,total_selected=counter,admin=True)


    if counter<1 :
        services_name=text_reservation_init
    text=f"{services_name}"
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)
    
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services_choosing']=services
        data['services_name']=services_name
        data['counter']=counter


#### admin end of selection reserve
@bot.callback_query_handler(func=lambda call: call.data == ("admin_make_reservation"))
def callback_query(call:CallbackQuery):
        # generate waiting markup
    markup = InlineKeyboardMarkup()
    waiting_button = InlineKeyboardButton("لطفا صبر کنید", callback_data=f"!!!!!!!!!!!!!!!!!!!!!!!!!")
    markup.add(waiting_button)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)

    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services=data['services_choosing']
    total_time = timedelta()
    total_price = 0  
    for service in services:
        if service[5]==1:
            total_time += service[2]  
            total_price += service[3] 
    #show days
    markup=makrup_generate_empty_time_of_day(delete_day=0,admin=True)
    text=text_admin_custom_select_day
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
    
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services_choosing']=services 
        data['total_time']=total_time
        data['total_price']=total_price

##show reserve and send start time 
@bot.callback_query_handler(func= lambda m:m.data.startswith("customReserve"))
def convertUserID(call:CallbackQuery):
    date=call.data.split(":")[1]
    GenerateSelectedDay(selected_date=date)
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services =data['services_choosing']
        total_time=data['total_time']
        total_price=data['total_price']
    text=text_send_start_time_msg
 # show times
    date_persian = convertDateToPersianCalendar(date=date)
    list_empty_time=calculate_empty_time_and_reserved_time(date=date)
    if list_empty_time not in [False,'False',[], None , 'None'] : 
            text+=f'\n📅 {date_persian}\n'
            for i in range(len(list_empty_time)):
                first_time =str(list_empty_time[i][0])
                end_time =str(list_empty_time[i][1])
                activation = int(list_empty_time[i][2])
                first_time_without_seconds = first_time[:5]
                end_time_without_seconds = end_time[:5]
                if activation == 0:
                    text += f'⏰ {first_time_without_seconds} الی {end_time_without_seconds} 🆓\n'
    bot.send_message(chat_id=call.message.chat.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.custom_reserve_start_time,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services_choosing']=services 
        data['total_time']=total_time
        data['total_price']=total_price
        data['date']=date


### get start time
@bot.message_handler(state=admin_State.custom_reserve_start_time)
def msg_handler(msg : Message):
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        date=data['date']
    
    # #send day reserve info to user
    # reserves=db_Reserve_Get_Reserve_Of_Date(date=date)
    # reserve_info_text=''
    # for reserve in reserves:
    #     reserve_info_text=f"{text} \n {text_user_reserve_info(reserve)}"
    # bot.send_message(chat_id=msg.from_user.id,text=text)

    # check to be start)time like 09:00
    pattern =r'^([01]\d|2[0-3]):(00|15|30|45)$'
    match = re.match(pattern, msg.text)
    # check input should be like HH:MM/HH:MM
    if not match:
        bot.send_message(chat_id=msg.chat.id, text=text_time_is_not_valid)
        return
    #check time validation 
    start_time=f"{msg.text}:01"
    list_empty_time=calculate_empty_time_and_reserved_time(date=date)
    valid_time=False
    for free_time in list_empty_time:
        if  free_time[2]=='0' and compare_time(lower=free_time[0],than=start_time ) and compare_time(lower=start_time,than=free_time[1] ):
            valid_time = compare_time(lower=free_time[0],than=start_time )
            if valid_time :
                break


    if not valid_time :
        text=text_time_is_not_valid
        bot.send_message(chat_id=msg.from_user.id,text=text)
        return



    text=text_please_send_end_time
    bot.send_message(chat_id=msg.from_user.id,text=text)
    bot.set_state(user_id=msg.chat.id,state=admin_State.custom_reserve_end_time,chat_id=msg.chat.id)
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        data['start_time']=start_time



####get end time
@bot.message_handler(state=admin_State.custom_reserve_end_time)
def msg_handler(msg : Message):
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        start_time=data['start_time']
        date=data['date']

    pattern =r'^([01]\d|2[0-3]):(00|15|30|45)$'
    match = re.match(pattern, msg.text)
    # check input should be like HH:MM/HH:MM
    if not match:
        bot.send_message(chat_id=msg.chat.id, text=text_time_is_not_valid)
        return
    #check time validation 
    end_time=f"{msg.text}:00"

    list_empty_time=calculate_empty_time_and_reserved_time(date=date)
    valid_time=False
    for free_time in list_empty_time:
        if free_time[2]=='0' and compare_time(lower=free_time[0],than=start_time ) and compare_time(lower=start_time,than=free_time[1] ):
           valid_time=compare_time(lower=f"{end_time}",than=f"{free_time[1]}")
           if valid_time:
               break

    if not valid_time :
        text=text_time_is_not_valid
        bot.send_message(chat_id=msg.from_user.id,text=text)
        return


    #save info to db 
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        start_time=data['start_time']
        services =data['services_choosing']
        user_id=msg.from_user.id
        price=data['total_price']
        date=data['date']
        duration=time_difference(time1=f"{start_time}",time2=f"{end_time}")
    result,reserve_id=db_make_reserve_transaction(date=date,duration=f"{duration}",price=price,
                                services=services,start_time=f"{start_time}",user_id=user_id)
    
    text=text_cleaner_info_reserve(date=date , start_time=start_time) 
    text=f'{text_reserve_custom_is_done}\n\n{text}'
    bot.send_message(chat_id=msg.from_user.id,text=text)
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    
############################################################################################ markup bot_setting
@bot.message_handler(func= lambda m:m.text == mark_text_admin_bot_setting)
def bot_setting(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False    
    text=text_bot_setting
    markup = markup_admin_bot_setting(bot_is_enable=bot_is_enable)
    bot.send_message(chat_id=msg.from_user.id,text=text,reply_markup=markup)


### change card info 
@bot.callback_query_handler(func= lambda m:m.data ==("change_cart_info"))
def change_cart_info(call:CallbackQuery):


    bot.delete_message(chat_id=call.message.chat.id,message_id=call.message.id)
    text=get_card_info()

    text=f"{text}\n\n{text_send_card_name}"
    bot.send_message(chat_id=call.message.chat.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.get_card_number,chat_id=call.message.chat.id)
    
####number id done => get bank name 
@bot.message_handler(state=admin_State.get_card_number)
def setWork_section_state_get_part1(msg : Message):
    card_number=str(msg.text)
    result = (len(card_number) == 16)
    if not result:
        text=text_card_number_is_not_valid
        bot.send_message(chat_id=msg.chat.id,text=text)
        return

    text=text_send_card_bank_name
    bot.send_message(chat_id=msg.chat.id,text=text)
    bot.set_state(user_id=msg.chat.id,state=admin_State.get_card_bank_name,chat_id=msg.chat.id)
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        data['card_number']=card_number
    
## bank_name is done : get owner name 
@bot.message_handler(state=admin_State.get_card_bank_name)
def setWork_section_state_get_part1(msg : Message):
    card_bank_name=str(msg.text)

    text=text_send_card_bank_owner
    bot.send_message(chat_id=msg.chat.id,text=text)
    bot.set_state(user_id=msg.chat.id,state=admin_State.get_card_owner_name,chat_id=msg.chat.id)
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        data['card_bank_name']=card_bank_name

        
## card_owner is done save info in db 
@bot.message_handler(state=admin_State.get_card_owner_name)
def setWork_section_state_get_part1(msg : Message):
    card_bank_owner=str(msg.text)
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        card_bank_name=data['card_bank_name']
        card_number=data['card_number']
    result =db_bot_setting_update(name="cart",new_value=card_number)
    if result:
        result = db_bot_setting_update(name="cart_name",new_value=card_bank_owner)
    if result :
        result =db_bot_setting_update(name="cart_bank",new_value=card_bank_name)
    if not result:
        text=text_problem_with_save_card_info
        bot.send_message(chat_id=msg.chat.id,text=text)
        return 
    
    text=get_card_info()
    text=f'{text}/n{text_info_is_saved}'
    bot.send_message(chat_id=msg.chat.id,text=text)
    

  ########################################################################  
### change_bot_enable_disable
## change welcome message
@bot.callback_query_handler(func= lambda m:m.data ==("welcome_message"))
def welcome_message(call:CallbackQuery):
    text=text_bot_setting_change_welcome_message
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_change_welcome_message,chat_id=call.message.chat.id)

@bot.message_handler(state=admin_State.state_change_welcome_message)
def setWork_section_state_get_part1(msg : Message):
    db_bot_setting_update(name='welcome_message' , new_value=msg.text)
    text= text_bot_setting_changed_welcome_message
    bot.send_message(chat_id=msg.from_user.id,text=text)
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  

### change_bo
# t_enable_disable
@bot.callback_query_handler(func= lambda m:m.data ==("change_bot_enable_disable"))
def convertUserID(call:CallbackQuery):
    value= "0" if bot_is_enable else "1"
    db_bot_setting_update(name="bot_is_enable",new_value=value)
    toggle_bot_status()
    bot_status =['غیرفعال ❌','فعال ✅']
    text=f'ربات برای کاربران عادی {bot_status[int(value)]} شد'
    markup = markup_admin_bot_setting(bot_is_enable=bot_is_enable)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)

##########admin list
@bot.callback_query_handler(func= lambda m:m.data ==("change_admin_list"))
def convertUserID(call:CallbackQuery):
    markup=InlineKeyboardMarkup()

    admin_list=db_admin_get_all()
    markup=markup_show_admin_list(admin_list)
    
    text=text_show_admin_setting
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
####### add admin
@bot.callback_query_handler(func= lambda m:m.data ==("admin_list_add"))
def convertUserID(call:CallbackQuery):
    text=text_add_admin_msg
    bot.send_message(chat_id=call.message.chat.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_add_admin,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['msg_id']=call.message.id

@bot.message_handler(state=admin_State.state_add_admin)
def setWork_section_state_get_part1(msg : Message):
    admin_id=int(msg.text)
    user_id_is_valid=db_Users_Validation_User_By_Id(admin_id)
    
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        msg_id=data['msg_id']
    if not user_id_is_valid:
        text=text_user_id_is_not_valid
        bot.delete_message(chat_id=msg.chat.id,message_id=msg_id)

        bot.send_message(chat_id=msg.chat.id,text=text)
        return 
    
    admin_add= db_admin_add(admin_id=admin_id)
    if admin_add:
        text=text_admin_is_added
    else:
        text=text_admin_is_not_added  
    
    markup=markup_admin_bot_setting()  

    bot.delete_message(chat_id=msg.chat.id,message_id=msg_id)
    bot.send_message(chat_id=msg.chat.id,text=text,reply_markup=markup)
####### show one admin info
@bot.callback_query_handler(func= lambda m:m.data.startswith("adminList_"))
def convertUserID(call:CallbackQuery):
    admin_id=int(call.data.split('_')[1])
    admin_is_mainAdmin=bool(call.data.split('_')[2])
    user=db_Users_Find_User_By_Id(admin_id)
    text=text_make_admin_info(admin=user,is_mainAdmin=admin_is_mainAdmin)
    markup=InlineKeyboardMarkup()
    if not admin_is_mainAdmin:
        btn1=InlineKeyboardButton(text=markup_text_remove_admin,callback_data=f"adminRemove_{admin_id}")
        markup.add(btn1)
        btn2=InlineKeyboardButton(text=markup_text_change_main_admin,callback_data=f"adminPromoteToMain_{admin_id}")
        markup.add(btn2)   
    if admin_is_mainAdmin :
        btn3=InlineKeyboardButton(text=markup_text_no_change_for_main_admin,callback_data=f"!!!!!!!")
        markup.add(btn3)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
####### promote admin to main_admin
@bot.callback_query_handler(func= lambda m:m.data.startswith("adminPromoteToMain_"))
def convertUserID(call:CallbackQuery):
    admin_id=int(call.data.split('_')[1])
    db_admin_set_main_admin(admin_id=admin_id)
    admin_list=db_admin_get_all()
    markup=markup_show_admin_list(admin_list)
    text=text_show_admin_setting
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
    
######remove admin 
@bot.callback_query_handler(func= lambda m:m.data.startswith("adminRemove_"))
def convertUserID(call:CallbackQuery):   
    admin_id=int(call.data.split('_')[1])
    result =db_admin_remove_admin(admin_id=admin_id)
    if result:
        text=text_admin_is_deleted
    else:
        text=text_error_call_to_support
    admin_list=db_admin_get_all()
    markup=markup_show_admin_list(admin_list)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)
    
############################################################################################ markup reserve time
@bot.message_handler(func= lambda m:m.text == mark_text_admin_reserved_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False 
    reserves=get_reserves_for_admin(days=10)
    markup=InlineKeyboardMarkup()
    if len(reserves) <1 :
        markup.add(InlineKeyboardButton(text=text_no_reserve_for_user,callback_data="!!!!!!"))
    else:
        for reserve in reserves:
            reserve_id=(f"{reserve['id']}")
            user_id=(f"{reserve['user_id']}")
            date=gregorian_to_jalali(f"{reserve['date']}")
            start_time=convert_to_standard_time(f"{reserve['start_time']}")[:5]
            end_time=convert_to_standard_time(f"{reserve['end_time']}")[:5]
            payment=(reserve['payment'])
            weekday=get_weekday(f"{reserve['date']}")
            text=f"{date} : {start_time}->{end_time} : {payment} HT : {weekday} "
            btn=InlineKeyboardButton(text=text,callback_data=f"show_reserve_info_{reserve_id}_{user_id}")
            markup.add(btn)
    bot.send_message(chat_id=msg.from_user.id,text=text_reserve_list_msg,reply_markup=markup)

@bot.callback_query_handler(func= lambda m:m.data.startswith("show_reserve_info"))
def convertUserID(call:CallbackQuery):
    reserve_id=call.data.split('_')[3]
    users_id=call.data.split('_')[4]

    text=make_reservation_info_text_for_admin(reserve_id=reserve_id,user_id=users_id,admin=True)
    markup=InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="پیام دادن به کاربر",url=f"tg://user?id={users_id}"))
    bot.send_message(chat_id=call.message.chat.id,text=text,reply_markup=markup)
############################################################################################ markup empty time
@bot.message_handler(func= lambda m:m.text == mark_text_admin_empty_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False    
    #every date when sent to markup will be delete ,so at first time i send a confusing value 
    markup = makrup_generate_empty_time_of_day(delete_day='0')
    text=text_get_empty_time
    bot.send_message(chat_id=msg.from_user.id,text=text , reply_markup=markup)

##### handle show empty time
@bot.callback_query_handler(func= lambda m:m.data.startswith("getEmptyTime:"))
def convertUserID(call:CallbackQuery):
    GenerateNext7Day()
    date=call.data.split(':')[1]
    GenerateSelectedDay(selected_date=date)

    date_persian = convertDateToPersianCalendar(date=date)
    # list_empty_time=[]
    list_empty_time=calculate_empty_time_and_reserved_time(date=date)
    markup = InlineKeyboardMarkup()
    if list_empty_time not in [False,'False',[], None , 'None'] : 
        text=f'📅 {date_persian}\n\n'
        count_reserve_time=0
        for i in range(len(list_empty_time)):
            first_time =str(list_empty_time[i][0])
            end_time =str(list_empty_time[i][1])
            activation = int(list_empty_time[i][2])
            first_time_without_seconds = first_time[:5]
            end_time_without_seconds = end_time[:5]
            if activation == 1:
                data_reserve=db_reserve_get_info_reserve_by_date_and_start_time(date=date , start_time=first_time)
                user_id=data_reserve[1]
                data_info=db_Users_Find_User_By_Id(user_id)
                name=data_info[4]
                text_button=f'💅🏼 {first_time_without_seconds} الی {end_time_without_seconds}  {name}'
                button = InlineKeyboardButton(text=text_button ,callback_data=f'getInfoReserved_{date}_{user_id}_{first_time}')
                markup.add(button)
                count_reserve_time+=1
            if activation == 0:
                text += f'{first_time_without_seconds} الی {end_time_without_seconds} 🆓\n'
        if count_reserve_time==0:
            text_button=text_et_empty_time_is_false
            button = InlineKeyboardButton(text=text_button ,callback_data=f'!!!!!!!')
            markup.add(button)
        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)
    else:
        markup = makrup_generate_empty_time_of_day(delete_day=str(date))
        text = f'📅 {date_persian}\n{text_empty_time_error_null}'
        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)




########################################## change days in markup next or previous 7 days
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_days"))
def change_days_callback(call):
    # generate waiting markup
    markup = InlineKeyboardMarkup()
    waiting_button = InlineKeyboardButton("لطفا صبر کنید", callback_data=f"!!!!!!!!!!!!!!!!!!!!!!!!!")
    markup.add(waiting_button)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)


    start_offset = int(call.data.split(":")[1])  # Extract new offset
    adminStr = str(call.data.split(":")[2])  # Extract new offset
    admin=True if adminStr=='True' else False
    markup = makrup_generate_empty_time_of_day(delete_day='0', start_offset=start_offset , admin = admin)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)

########################################## get information of select reservation 
#input is data, user_id, star_time, end_time and make and send message with markup 
@bot.callback_query_handler(func= lambda m:m.data.startswith("getInfoReserved_"))
def getInfoReservation(call:CallbackQuery):
    date=call.data.split('_')[1]
    user_id=call.data.split('_')[2]
    start_time=call.data.split('_')[3]
    text_reserve =text_cleaner_info_reserve(date=date , start_time=start_time) 
    id_reserved=db_reserve_get_info_reserve_by_date_and_start_time(date=date , start_time=start_time)
    id_reserved = int(id_reserved[0])
    data_user=db_Users_Find_User_By_Id(user_id)
    text_user = text_cleaner_info_user(data=data_user)
    text = f'{text_reserve}\n\n اطلاعات کاربر 👩🏼‍🦰\n{text_user}'
    markup = InlineKeyboardMarkup()
    markup = makrup_generate_empty_time_of_day(delete_day='0')
    button = InlineKeyboardButton(text='❌ 🗑 حذف رزرو 🗑 ❌',callback_data=f'deleteReservedTime_{id_reserved}_{date}_{start_time}')
    markup.add(button)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)
########################################## delete reservation
@bot.callback_query_handler(func= lambda m:m.data.startswith("deleteReservedTime_"))
def deleteReservedTime(call:CallbackQuery):
    id_reserve=call.data.split('_')[1] 
    date=call.data.split('_')[2]
    start_time=call.data.split('_')[3]   
    text = f'{text_delete_reserve}'
    reserved_data = db_Reserve_Get_Reserve_With_Id(id_reserve)
    user_data=db_Users_Find_User_By_Id(reserved_data[1])
    text_user = text_cleaner_info_user(data=user_data)
    text_info= text_cleaner_info_reserve(date=date , start_time=start_time)
    text =f'{text_delete_reserve}\n{text_info}\n{text_user}'
    db_Reserve_Delete_Reserve(id_reserve)
    markup = InlineKeyboardMarkup()
    markup = makrup_generate_empty_time_of_day(delete_day='0')
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)

############################################################################################ markup set work time
@bot.message_handler(func= lambda m:m.text == mark_text_admin_set_work_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.chat.id,text=text_user_is_not_admin)
        return False
    markup = InlineKeyboardMarkup()
    markup=makrup_generate_set_work_list_of_days()
    text=text_set_work_time_get_date
    bot.send_message(chat_id=msg.chat.id,text=text, reply_markup=markup)
##########################################  call date from admin to set work 
@bot.callback_query_handler(func= lambda m:m.data.startswith("SetWorkTime:"))
def convertUserID(call:CallbackQuery):
    date=call.data.split(':')[1]
    markup = InlineKeyboardMarkup()
    markup = makrup_generate_parts_list_of_set_work(date=date)
    date_text=convertDateToPersianCalendar(date=str(date))
    text = f'📅 {date_text}'
    #check activation of day if day be disable , admin can change day status
    date_as_day=convertDateToDayAsGregorianCalendar(date=date)
    check_is_active_day=db_WeeklySetting_Get_Value_one_day(name=date_as_day)
    if check_is_active_day[2] =='0':
        text =f'📅 {text} \n {text_error_disable_day}'
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)
#########################################   change days in calendare
@bot.callback_query_handler(func=lambda call: call.data.startswith("setworktime_change_days"))
def change_days_callback(call):
    # generate waiting markup
    markup = InlineKeyboardMarkup()
    waiting_button = InlineKeyboardButton("لطفا صبر کنید", callback_data=f"!!!!!!!!!!!!!!!!!!!!!!!!!")
    markup.add(waiting_button)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)


    start_offset = int(call.data.split(":")[1])  # Extract new offset
    markup = makrup_generate_set_work_list_of_days(offset=start_offset)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)


#########################################  call update setWork part1
@bot.callback_query_handler(func= lambda m:m.data.startswith("SetWorkUpdatePart:"))
def forwardToStateUpdatePart(call:CallbackQuery):
    part=call.data.split(':')[1]
    date=call.data.split(':')[2]
    persian_date=convertDateToPersianCalendar(date)
    text_array=['صبح ☀️ ','عصر 🌙']
    text = f'📅 {persian_date} {text_array[int(part)-1]}\n{text_set_work_time_get_part}'

    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_setWork_update_part,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['date1']=date
        data['part']=part

# state update setwork part
@bot.message_handler(state=admin_State.state_setWork_update_part)
def setWork_section_state_update_part1(msg : Message):
    try:
        duration=str(msg.text)
        ##Regular expression pattern to match the format 'HH:MM:01/HH:MM:00' and min=[00,15,45]
        pattern =r'^([01]\d|2[0-3]):(00|15|30|45)/([01]\d|2[0-3]):(00|15|30|45)$'
        match = re.match(pattern, duration)
        # check input should be like HH:MM/HH:MM
        if not match:
            bot.send_message(chat_id=msg.chat.id, text=text_set_work_time_get_part)
            return
        start_time_without_seconds=str(duration.split('/')[0])
        end_time_without_seconds=str(duration.split('/')[1])
        start_time=start_time_without_seconds+f':01'
        end_time=end_time_without_seconds+f':00'
        time_format = "%H:%M:%S"
        check_start_time = datetime.strptime(start_time, time_format).time()
        check_end_time = datetime.strptime(end_time, time_format).time()
        # end time should be after start time
        if not check_start_time < check_end_time:
            bot.send_message(chat_id=msg.chat.id, text=text_set_work_error_input_compare_parts)
            return
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id) as data:
            date1=str(data['date1'])
            part=int(data['part'])
            #when you update part1 and part 2 have time ->par1 should be before part2
            if part == 1:
                part2=db_SetWork_Get_Part1_or_Part2_of_Day(date=date1 , part=2)
                if part2[0] not in [None , 'None',False ,'False'] :
                    part2_start_time = str(part2[0])
                    part2_start_time_without_second = part2_start_time[:5]
                    time_format = "%H:%M:%S"
                    check_start_time = datetime.strptime(part2_start_time, time_format).time()
                    check_end_time = datetime.strptime(end_time, time_format).time()
                    if not check_end_time<check_start_time :
                        bot.send_message(chat_id=msg.chat.id, text=f' پارت وارد شده باید تا قبل از ساعت {part2_start_time_without_second} باشد\n لطفا مجدد بازه را ارسال کنید ')
                        return
             #when you update part2 and part1 have time ->par2 should nbe after part1
            if part == 2:
                part1=db_SetWork_Get_Part1_or_Part2_of_Day(date=date1 , part=1)
                if part1[0] not in [None , 'None',False ,'False'] :
                    part1_end_time = str(part1[1])
                    part1_end_time_without_second = part1_end_time[:5]
                    time_format = "%H:%M:%S"
                    check_start_time = datetime.strptime(start_time, time_format).time()
                    check_end_time = datetime.strptime(part1_end_time, time_format).time()
                    if not check_start_time>check_end_time :
                        bot.send_message(chat_id=msg.chat.id, text=f' پارت وارد شده باید تا بعد از ساعت {part1_end_time_without_second} باشد\n لطفا مجدد بازه را ارسال کنید ')
                        return
            result=db_SetWork_Update_One_Part_Of_Day(date=date1 , part=part , start_time=start_time ,end_time=end_time)
            persian_date=convertDateToPersianCalendar(date1)
            text_part=['صبح ☀️ ','عصر 🌙']
            text = f'📅 {persian_date} {text_part[part-1]}\n{start_time_without_seconds} الی {end_time_without_seconds} با ثبت  شد '
            markup = InlineKeyboardMarkup()
            markup= makrup_generate_set_work_list_of_days()
            bot.send_message(chat_id=msg.chat.id, text=text , reply_markup=markup)
        bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    #except ValueError:
    #    bot.send_message(chat_id=msg.chat.id, text=text_set_work_error_input_compare_parts)
    except Error as e:
        logging.error(f"reserveValidId : {e}")
        return False
############################################################################################
@bot.callback_query_handler(func= lambda m:m.data.startswith("SetWorkDeletePart:"))
def forwardToStateUpdatePart(call:CallbackQuery):
    part=call.data.split(':')[1]
    date=call.data.split(':')[2]
    db_SetWork_Delete_One_Part(part=part , date=date)
    markup=makrup_generate_set_work_list_of_days()
    persian_date=convertDateToPersianCalendar(date=date)
    text_part=['صبح ☀️ ','عصر 🌙']
    text= f'📅 {persian_date} {text_part[int(part)-1]} با موفقیت حذف شد'
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
############################################################################################ markup weekly time
@bot.message_handler(func= lambda m:m.text == mark_text_admin_weekly_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.chat.id,text=text_user_is_not_admin)
        return False
    markup = makrup_generate_weekly_time_list()
    bot.send_message(chat_id=msg.chat.id,text=text_weekly_time, reply_markup=markup)
#########################################  get name to change value                   
@bot.callback_query_handler(func= lambda m:m.data.startswith("weeklysetting:"))
def forwardToStateUpdatePart(call:CallbackQuery):
    bot.delete_state(user_id=call.message.id,chat_id=call.message.chat.id) 
    name = str(call.data.split(':')[1])
    data= db_WeeklySetting_Get_Value_one_day(name=name)
    value=data[2]
    name_persian=ConvertVariableInWeeklySettingToPersian(name)
    if value == '1':
        db_WeeklySetting_Update(name=name , value='0' )
        text=f'{name_persian} غیر فعال ❌ شد '
        markup = makrup_generate_weekly_time_list()
        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
    if value =='0':   
        db_WeeklySetting_Update(name=name , value='1' )
        text=f'{name_persian} فعال ✅ شد '
        markup = makrup_generate_weekly_time_list()
        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
    if value =='None':
        text=f'زمان خود را برای تعیین پیش فرض <b>{name_persian}</b> وارد کنید :\n' + text_set_work_time_get_part
        value_text=ConvertVariableInWeeklySettingToPersian(value)
        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text)
        bot.set_state(user_id=call.message.chat.id,state=admin_State.state_weekly_update_time,chat_id=call.message.chat.id)
        with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
            data['name']= name
    if value not in ['0' , '1' , 'None'] :
        text=f'زمان خود را برای تعیین پیش فرض <b>{name_persian}</b> وارد کنید \nدر صورت نیاز به حذف از دکمه زیر استفاده کنید\n' + text_set_work_time_get_part
        markup = InlineKeyboardMarkup()
        value_text=ConvertVariableInWeeklySettingToPersian(value)
        if value != 'None' :
            button_delete = InlineKeyboardButton(text=f'🗑 حذف {value_text} 🗑' ,callback_data=f'WeeklyDeletePart:{name}')
            markup.add(button_delete)
            bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
        bot.set_state(user_id=call.message.chat.id,state=admin_State.state_weekly_update_time,chat_id=call.message.chat.id)
        with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
            data['name']= name

#########################################  get name to delete value                   
@bot.callback_query_handler(func= lambda m:m.data.startswith("WeeklyDeletePart:"))
def weeklySettingDeletePartFrom(call:CallbackQuery):
    name = str(call.data.split(':')[1])
    name_persian=ConvertVariableInWeeklySettingToPersian(name)
    text = f'حذف {name_persian} انجام شد'
    db_WeeklySetting_Update(name=name , value='None')
    markup = makrup_generate_weekly_time_list()
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text , reply_markup=markup)
######################################### state to get part for change value in default week setting  
@bot.message_handler(state=admin_State.state_weekly_update_time)
def weekly_time_section_state_update_value(msg : Message):
    try:
        part=msg.text
        pattern =r'^([01]\d|2[0-3]):(00|15|30|45)/([01]\d|2[0-3]):(00|15|30|45)$'
        match = re.match(pattern, part)
        if not match:
            bot.send_message(chat_id=msg.chat.id, text=text_set_work_time_get_part)
            return
        start_time=str(part.split('/')[0])+f':01'
        end_time=str(part.split('/')[1])+f':00'
        time_format = "%H:%M:%S"
        check_start_time = datetime.strptime(start_time, time_format).time()
        check_end_time = datetime.strptime(end_time, time_format).time()
        if not check_start_time < check_end_time:
            bot.send_message(chat_id=msg.chat.id, text=text_set_work_error_input_compare_parts)
            return
        with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
            name=str(data['name'])
            part = f'{start_time}/{check_end_time}'
            if name == 'part1':
               parts=db_WeeklySetting_Get_Parts()
               part2 = str(parts[1][1])
               part2_start_time = str(part2.split('/')[0])
               part2_start_time_without_second = part2_start_time[:5]
               if part2 not in [None , 'None'] :
                   time_format = "%H:%M:%S"
                   check_start_time = datetime.strptime(part2_start_time, time_format).time()
                   check_end_time = datetime.strptime(end_time, time_format).time()
                   if not check_end_time<check_start_time :
                       bot.send_message(chat_id=msg.chat.id, text=f' پارت وارد شده باید تا قبل از ساعت {part2_start_time_without_second} باشد\n لطفا مجدد بازه را ارسال کنید ')
                       return
    
            #when you update part2 and part1 have time ->par2 should nbe after part1
            if name == 'part2':
               parts=db_WeeklySetting_Get_Parts()
               part1 = str(parts[0][1])
               part1_end_time = str(part1.split('/')[1])
               part1_start_time_without_second = part1_end_time[:5]
               if part1 not in [None , 'None'] :
                   time_format = "%H:%M:%S"
                   check_start_time = datetime.strptime(start_time, time_format).time()
                   check_end_time = datetime.strptime(part1_end_time, time_format).time()
                   if not check_end_time<check_start_time :
                       bot.send_message(chat_id=msg.chat.id, text=f' پارت وارد شده باید تا بعد از ساعت {part1_start_time_without_second} باشد\n لطفا مجدد بازه را ارسال کنید ')
                       return

            db_WeeklySetting_Update(name , part)
            name_persian=ConvertVariableInWeeklySettingToPersian(name)
            part=ConvertVariableInWeeklySettingToPersian(part)
            text=f'{name_persian} به {part} تغییر کرد'
            markup = makrup_generate_weekly_time_list()
            bot.send_message(chat_id=msg.chat.id,text=text, reply_markup=markup)
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_set_work_time_get_part)
############################################################################################ markup set service
@bot.message_handler(func= lambda m:m.text == mark_text_admin_set_service)
def reserve_time(msg : Message): 
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False    
    markupText = text_admin_update_service
    serviceData=list(db_Service_Get_All_Services())
    sorted_serviceData_by_price = sorted(serviceData, key=lambda item: item[3], reverse=True)
    sorted_serviceData_by_price_then_by_activation = sorted(sorted_serviceData_by_price, key=lambda item: item[4], reverse=True)
    markup=makrup_generate_service_list(sorted_serviceData_by_price_then_by_activation)
    bot.send_message(chat_id=msg.chat.id,text=markupText, reply_markup=markup)
###########################################   insert service
@bot.callback_query_handler(func=lambda call: call.data == mark_text_admin_service_insert)
def callback_query(call : CallbackQuery):
    if not validation_admin(call.message.chat.id) : 
        bot.send_message(chat_id=call.message.chat.id,text=text_user_is_not_admin)
        return False
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_update_service_name)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_service_enter_name,chat_id=call.message.chat.id)

#get name for new service
@bot.message_handler(state=admin_State.state_service_enter_name)
def service_section_state_enter_name(msg : Message):
    service_name=msg.text
    if db_Service_Get_Service_With_Name(service_name=service_name) is not None :
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_name_duplicated)
        return False
    with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id) as data:
        data['service_name']=service_name
    bot.set_state(user_id=msg.chat.id,state=admin_State.state_service_enter_time_slots,chat_id=msg.chat.id)
    bot.send_message(chat_id=msg.chat.id,text=text_update_service_time_slots)

#get Time for new service
@bot.message_handler(state=admin_State.state_service_enter_time_slots)
def service_section_state_enter_time_slots(msg : Message):
    try:
        pattern =r'^([01]\d|2[0-3]):(00|15|30|45)$'
        match = re.match(pattern, msg.text)
        if not match:
            bot.send_message(chat_id=msg.chat.id, text=text_update_service_error_time)
            return
        timeOfService=f"{msg.text}:00"
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id) as data:
            data['service_time']=timeOfService
        bot.set_state(user_id=msg.chat.id,state=admin_State.state_service_enter_price,chat_id=msg.chat.id)
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_price)
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_time)
        return False
   

#get price for new service
@bot.message_handler(state=admin_State.state_service_enter_price)
def service_section_state_enter_price(msg : Message):
    try:
        service_price=int(msg.text)
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id) as data:
            data['service_price']=service_price   
        bot.set_state(user_id=msg.chat.id,state=admin_State.state_service_enter_is_active,chat_id=msg.chat.id)
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_is_active)
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_price)

#get is_active for new service insert in db 
@bot.message_handler(state=admin_State.state_service_enter_is_active)
def service_section_state_enter_price(msg : Message):
    try:
        service_is_active_int = int(msg.text)
        if service_is_active_int ==0 or service_is_active_int ==1:
            service_is_active=bool(service_is_active_int)
        else:
            bot.send_message(msg.chat.id,text=text_update_service_error_is_active)
            return False 
        
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id) as data:
            data['service_is_active']=service_is_active_int
            service_name =str(data['service_name'])
            service_time =(data['service_time'])
            service_price =int(data['service_price'])
            service_is_active_int =bool(data['service_is_active'])
        service_id =db_Service_Insert_Service(name=service_name ,time=service_time , price=service_price , is_active=service_is_active_int )
        service_info= createLabelServicesToShowOnButton(int(service_id))

        serviceData=list(db_Service_Get_All_Services())
        sorted_serviceData_by_price = sorted(serviceData, key=lambda item: item[3], reverse=True)
        sorted_serviceData_by_price_then_by_activation = sorted(sorted_serviceData_by_price, key=lambda item: item[4], reverse=True)
        markup=makrup_generate_service_list(sorted_serviceData_by_price_then_by_activation)
        
        text=f"{text_update_service_enter_all_info}\n{service_info} "
        bot.send_message(chat_id=msg.chat.id,text=text,reply_markup=markup)
        bot.delete_state(user_id=msg.chat.id,chat_id=msg.chat.id) 
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_is_active)

###########################################  get list services
@bot.callback_query_handler(func= lambda m:m.data.startswith("showServiceList_"))
def convertServiceID(call:CallbackQuery):

    ServiceID=int(call.data.split('_')[1])
    markup =markup_generate_service(ServiceID)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=createLabelServicesToShowOnButton(ServiceID), reply_markup=markup)


#### markup Update name Service Panel
@bot.callback_query_handler(func= lambda m:m.data.startswith("editServiceName_"))
def service_update_name(call:CallbackQuery):
    serviceid=int(call.data.split('_')[1])
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_update_service_name)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_service_update_name,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id,chat_id=call.message.chat.id) as data:
        data['service_id']= serviceid 
#### state Update Name Service Panel
@bot.message_handler(state=admin_State.state_service_update_name)
def service_section_update_name(msg : Message):
    with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id,) as data:
        serviceId = int(data['service_id'])
        db_Service_Update_Service_Name(service_id=serviceId , name=msg.text)
        showText=createLabelServicesToShowOnButton(serviceId)
        markup=markup_generate_service(serviceId)
        bot.send_message(chat_id=msg.chat.id,text=f'{showText}\nنام آیتم بالا با موفقیت تغییر کرد\n.',reply_markup=markup)
    bot.delete_state(user_id=msg.chat.id,chat_id=msg.chat.id)


#### markup Update time_slot Service Panel
@bot.callback_query_handler(func= lambda m:m.data.startswith("editServiceTimeSlot_"))
def service_update_timeSlot(call:CallbackQuery):
    serviceId=int(call.data.split('_')[1])
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_update_service_time_slots)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_service_update_time_slots,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id,chat_id=call.message.chat.id) as data:
        data['service_id']= serviceId
#### state Update time_slot Service Panel
@bot.message_handler(state=admin_State.state_service_update_time_slots)
def service_section_update_timeSlot(msg : Message):
    try:
        pattern =r'^([01]\d|2[0-3]):(00|15|30|45)$'
        match = re.match(pattern, msg.text)
        if not match:
            bot.send_message(chat_id=msg.chat.id, text=text_update_service_error_time)
            return
        timeOfService=f"{msg.text}:00"
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id,) as data:
            serviceId = int(data['service_id'])
            db_Service_Update_Service_Time(service_id=serviceId , time=timeOfService)
            showText=createLabelServicesToShowOnButton(serviceId)
            markup=markup_generate_service(serviceId)
            bot.send_message(chat_id=msg.chat.id,text=f'{showText}\n زمان آیتم بالا با موفقیت تغییر کرد\n.',reply_markup=markup)
        bot.delete_state(user_id=msg.chat.id,chat_id=msg.chat.id)
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_time)


#### markup Update price Service Panel
@bot.callback_query_handler(func= lambda m:m.data.startswith("editServicePrice_"))
def service_section_update_price(call:CallbackQuery):
    serviceId=int(call.data.split('_')[1])
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_update_service_price)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_service_update_price,chat_id=call.message.chat.id)
    with bot.retrieve_data(user_id=call.message.chat.id,chat_id=call.message.chat.id) as data:
        data['service_id']= serviceId
#### state Update price Service Panel
@bot.message_handler(state=admin_State.state_service_update_price)
def service_section_update_price(msg : Message):
    try:
        updated_price=int(msg.text)
        with bot.retrieve_data(user_id=msg.chat.id,chat_id=msg.chat.id,) as data:
            serviceId = int(data['service_id'])
            db_Service_Update_Service_Price(service_id=serviceId , price=updated_price)
            showText=createLabelServicesToShowOnButton(serviceId)
            markup=markup_generate_service(serviceId)
            bot.send_message(chat_id=msg.chat.id,text=f'{showText}\nقیمت آیتم بالا با موفقیت تغییر کرد\n.',reply_markup=markup)
        bot.delete_state(user_id=msg.chat.id,chat_id=msg.chat.id)
    except ValueError:
        bot.send_message(chat_id=msg.chat.id,text=text_update_service_error_price)




#### markup Update is_active Service Panel
@bot.callback_query_handler(func= lambda m:m.data.startswith("editServiceIsAcive_"))
def service_section_update_is_active(call:CallbackQuery):
    serviceId=int(call.data.split('_')[1])
    data=db_Service_Get_Is_Active_Services(serviceId)
    data_str="فعال"
    if data == 1 :
        data_str="غیرفعال"
        db_Service_Disable_Service(service_id=serviceId)
    else:
        db_Service_Enable_Service(serviceId)
    showText=createLabelServicesToShowOnButton(serviceId)
    markup=markup_generate_service(serviceId)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=f'{showText}\n آیتم بالا با موفقیت {data_str} شد\n.',reply_markup=markup)
    



#### markup delete Service Panel
@bot.callback_query_handler(func= lambda m:m.data.startswith("editServiceDelete_"))
def service_update_name(call:CallbackQuery):
    serviceId=int(call.data.split('_')[1])
    showText=createLabelServicesToShowOnButton(serviceId)
    db_Service_Delete_Service(service_id=serviceId)
    serviceData=list(db_Service_Get_All_Services())
    sorted_serviceData = sorted(serviceData, key=lambda item: item[4], reverse=True)
    markup=makrup_generate_service_list(sorted_serviceData)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=f'{showText}\nآیتم بالا با موفقیت حذف شد\n.',reply_markup=markup)
######################################################################## access to all users
@bot.message_handler(func= lambda m:m.text == mark_text_admin_users_list)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    if not validation_admin(msg.from_user.id) : 
        bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
        return False  
    markup=markup_generate_list_of_users(user_id_for_delete='0')
    text=text_users_list
    bot.send_message(chat_id=msg.chat.id,text=text, reply_markup=markup)


@bot.callback_query_handler(func= lambda m:m.data.startswith("showUsersList_"))
def showUserList(call:CallbackQuery):
    user_id=int(call.data.split('_')[1])
    text=accountInfoCreateTextToShow(user_id=user_id)
    markup=markup_generate_list_of_users(user_id_for_delete=user_id)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)

@bot.callback_query_handler(func= lambda m:m.data.startswith("searchForUser"))
def searchForUser(call:CallbackQuery):
    bot.set_state(user_id=call.message.chat.id,state=admin_State.state_user_find,chat_id=call.message.chat.id)
    text=text_user_find
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text)


@bot.message_handler(state=admin_State.state_user_find)
def user_section_user_find(msg : Message):
    if db_Users_Find_User_By_Id(user_id=msg.text) is False :
        bot.send_message(chat_id=msg.chat.id,text=text_user_not_find)
        return
    text = accountInfoCreateTextToShow(user_id=msg.text)
    bot.send_message(msg.chat.id,text, parse_mode='Markdown')
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 

###########################################  send message to all
@bot.message_handler(func=lambda m:m.text == mark_text_admin_send_message_to_all)
def msg_to_all(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)  
    if not validation_admin (msg.from_user.id):
         bot.send_message(chat_id=msg.from_user.id,text=text_user_is_not_admin)
         return False
    bot.send_message(msg.chat.id,text=text_message_to_all_users)
    bot.set_state(user_id=msg.from_user.id,state=admin_State.message_to_all,chat_id=msg.chat.id)


@bot.message_handler(state =admin_State.message_to_all)
def get_message_to_send(msg : Message):
    with bot.retrieve_data(msg.from_user.id,msg.chat.id) as data :
        data['msg']=msg.text
    text=f"یک پیام از سمت ادمین :\n <strong> {data['msg']} </strong> "
    users=db_Users_Get_All_Users()
    for user in users:
        try:
            bot.get_chat(user[0])
            bot.send_message(chat_id=user[0],text=text)
        except apihelper.ApiTelegramException as e:
            logging.error(f"user with ID {user[0]} not found to send message")
    bot.send_message(chat_id=msg.chat.id,text=text_sent_message_to_all_users)
    bot.delete_state(user_id= msg.from_user.id,chat_id=msg.chat.id)
###########################################
#######################################################################!   User Panel
#* /start
@bot.message_handler(commands=['start'])
def start(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if  not bot_is_enable:
        bot_is_disable(user_id=msg.from_user.id) 
        return
    user_id=msg.from_user.id
    user_is_valid=db_Users_Validation_User_By_Id(user_id=user_id)
    if user_is_valid is False :
        user_is_created =db_Users_Insert_New_User(user_id=msg.from_user.id,username=msg.from_user.username,join_date=datetime.now().date(),name='empty',phone_number='0')
        if user_is_created is False:
            text=text_user_not_created
            bot.send_message(chat_id=user_id,text=text,reply_markup=ReplyKeyboardRemove())
            return False
    
    markup=ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(mark_text_reserve_time)
    markup.add(mark_text_reserved_time)
    markup.add(mark_text_account_info ,mark_text_support)
    text=db_bot_setting_get_value_by_name(name='welcome_message')
    bot.send_message(chat_id=user_id,text=text,reply_markup=markup)
#######################################################################  see all reserve 
#* mark_text_reserved_time handler
@bot.message_handler(func= lambda m:m.text == mark_text_reserved_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    if not bot_is_enable:
        bot_is_disable(user_id=msg.from_user.id) 
        return

    user_id=msg.from_user.id
    reserves= get_reserves_for_user(user_id=user_id)
    reserves=sorted(reserves, key=lambda x: (x['date'], x['start_time']))

    markup=InlineKeyboardMarkup()
    if len(reserves) <1 :
        markup.add(InlineKeyboardButton(text=text_no_reserve_for_user,callback_data="!!!!"))
    else:
        markup=markup_generate_reserved_list(reserve_list=reserves , delete_reserve_id='0')
    bot.send_message(chat_id=user_id,text=text_reserve_list_msg,reply_markup=markup)

##########
# see more details
@bot.callback_query_handler(func=lambda call: call.data.startswith("userSeeReserve_"))
def callback_query(call:CallbackQuery):
    reserve_id=call.data.split("_")[1]
    user_id=call.data.split("_")[2]
    reserves= get_reserves_for_user(user_id=user_id)
    reserves=sorted(reserves, key=lambda x: (x['date'], x['start_time']))

    markup=InlineKeyboardMarkup()
    if len(reserves) <1 :
        markup.add(InlineKeyboardButton(text=text_no_reserve_for_user,callback_data="!!!!"))
    else:
        markup=markup_generate_reserved_list(reserve_list=reserves , delete_reserve_id=reserve_id)
    
    reserve=db_Reserve_Get_Reserve_With_Id(reserve_id=reserve_id)
    text=text_user_reserve_info(reserve=reserve)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)


####################################################################### Insert Reserve Time Section
#* mark_text_reserve_time handler
@bot.message_handler(func= lambda m:m.text == mark_text_reserve_time)
def reserve_time(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if not bot_is_enable: 
        bot_is_disable(user_id=msg.from_user.id) 
        return
    #update Username while every reservation
    db_Users_Update_Username_User(user_id=msg.from_user.id , username=msg.from_user.username)
    name = db_Users_Get_Name_User(msg.from_user.id)
    if name == 'empty' : 
        activation_user(msg=msg)
        return
    
    counter=0 
    services=db_Service_Get_All_Services()
    if services is None or len(services) ==0:
        bot.send_message(chat_id=msg.from_user.id,text=text_no_service_available)
        return False
    
    sorted_serviceData_by_price = sorted(services, key=lambda item: item[3], reverse=True)
    services = sorted(sorted_serviceData_by_price, key=lambda item: item[4], reverse=True)

    services = [service + (0,) for service in services]
    markup=markup_generate_services_for_reserve(services,total_selected=counter)

    text=text_reservation_init
    bot.send_message(chat_id=msg.chat.id,reply_markup=markup,text=text)

    bot.set_state(user_id=msg.chat.id,state=user_State.state_selecting_service,chat_id=msg.chat.id)


    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        data['services_choosing']=services
        data['services_name']=''
        data['counter']=counter
            

### select a service 
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_service_"))
def callback_query(call:CallbackQuery):
    service_id=(call.data.split("_"))[2]
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services=data['services_choosing']
        services_name=str(data["services_name"])
        counter=data['counter']
    # change enable <=> disable
    for index, service in enumerate(services):

        if int(service[0]) == int(service_id):
            if service[5]==0: # if service need to active
                if counter== 0:# if basic info not set
                    services_name="لیست خدمات انتخاب شده : "


                services[index]=service[:5] + (1,) 
                duration_time=convert_to_standard_time(f"{services[index][2]}")
                current_service_info=f"\n💅🏼 {services[index][1]} \n    💰 قیمت {services[index][3]} هزار تومان\n    ⏰ زمان موردنیاز {duration_time[:5]}"
                services_name=f"\n{services_name}\n {current_service_info}"
                counter=counter+1
            else:# if service wanna be disable
                services[index]=service[:5] + (0,) 
                duration_time=convert_to_standard_time(f"{services[index][2]}")
                current_service_info=f"\n💅🏼 {services[index][1]} \n    💰 قیمت {services[index][3]} هزار تومان\n    ⏰ زمان موردنیاز {duration_time[:5]}"
                services_name = services_name.replace(current_service_info, "").strip()
                counter=counter-1
            break
    markup=markup_generate_services_for_reserve(services,total_selected=counter)


    if counter==0 :
        services_name="لیست خدمات انتخاب شده : "
    text=f"{services_name}"
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text, reply_markup=markup)
    
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services_choosing']=services
        data['services_name']=services_name
        data['counter']=counter
    
####end of selection 
@bot.callback_query_handler(func=lambda call: call.data == ("make_reservation"))
def callback_query(call:CallbackQuery):
    # generate waiting markup
    markup = InlineKeyboardMarkup()
    waiting_button = InlineKeyboardButton("لطفا صبر کنید", callback_data=f"!!!!!!!!!!!!!!!!!!!!!!!!!")
    markup.add(waiting_button)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)

    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services=data['services_choosing']
    total_time = timedelta()
    total_price = 0  
    for service in services:
        if service[5]==1:
            total_time += service[2]  
            total_price += service[3] 
    #get list and sort by date 
    total_time=convert_to_standard_time(time_string=f"{total_time}") 
    available_day_list=get_free_time_for_next_7day(duration=total_time)
    available_day_list = sorted(available_day_list, key=lambda x: x[0])
    markup = markup_generate_days_for_reserve(available_day_list=available_day_list)
    
    text=text_make_reservation_info(price=total_price,time=total_time,services=services)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services_choosing']=services 
        data['total_time']=total_time
        data['total_price']=total_price

## btn is send pic
@bot.callback_query_handler(func=lambda call: call.data.startswith("user_panel_change_days"))
def callback_query(call:CallbackQuery):
    markup = InlineKeyboardMarkup()
    waiting_button = InlineKeyboardButton(" لطفا صبر کنید", callback_data=f"!!!!!!!!!!!!!!!!!!!!!!!!!")
    markup.add(waiting_button)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id,message_id=call.message.message_id,reply_markup=markup)

    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        total_time=data['total_time']
    text=call.message.text

    offset=int(call.data.split(":")[1])
    available_day_list=get_free_time_for_next_7day(duration=total_time,offset=offset)
    available_day_list = sorted(available_day_list, key=lambda x: x[0])

    markup = markup_generate_days_for_reserve(available_day_list=available_day_list,offset=offset)
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)



## btn is send pic 
@bot.callback_query_handler(func=lambda call: call.data.startswith("reserve_date_"))
def callback_query(call:CallbackQuery):
    date=(call.data.split("_")[2])
    time=(call.data.split("_")[3])
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services =data['services_choosing']
        total_time=data['total_time']
        total_price=data['total_price']
        #time + duration and result is end time to show for user
        start_time_obj = datetime.strptime(time, "%H:%M:%S")
        duration_parts = list(map(int, total_time.split(':')))
        duration_obj = timedelta(hours=duration_parts[0], minutes=duration_parts[1], seconds=duration_parts[2])
        end_time_obj = start_time_obj + duration_obj
        end_time = end_time_obj.strftime("%H:%M:%S")
    per_date=convertDateToPersianCalendar(date=date)
    text=make_reservation_info_text_for_user(date=per_date,start_time=time,price=total_price,end_time=end_time,services=services, )
    
    markup=InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="ارسال رسید 💳", callback_data="pic_receipt"))
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services']=services 
        data['total_time']=total_time
        data['total_price']=total_price
        data['date']=date
        data['time']=time
        data['start_time']=start_time_obj
        data['end_time']=end_time
        price = calculate_time_difference(time_str1=f"{start_time_obj}",time_str2=f"{end_time}")
        cart_info=text_cart_info(price)
        text=f'{text}\n{cart_info}'
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text,reply_markup=markup)

### get pic_receipt msg
@bot.callback_query_handler(func=lambda call: call.data == ("pic_receipt"))
def callback_query(call:CallbackQuery):
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        services =data['services']
        total_time=data['total_time']
        total_price=data['total_price']
        date=data['date']
        time=data['time']
    bot.delete_state(user_id=call.message.from_user.id,chat_id=call.message.chat.id)

    text=call.message.text
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text)
    
    text=text_send_receipt
    bot.send_message(chat_id=call.message.chat.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=user_State.get_rec,chat_id=call.message.chat.id)
    
    with bot.retrieve_data(user_id=call.message.chat.id , chat_id=call.message.chat.id) as data:
        data['services']=services 
        data['total_time']=total_time
        data['total_price']=total_price
        data['date']=date
        data['time']=time

## pic_receipt is sended not as pic
@bot.message_handler(state=user_State.get_rec, content_types=['text', 'video', 'document', 'audio', 'sticker', 'voice', 'location', 'contact'])
def handle_non_photo(msg: Message):
    # پیام خطا برای ارسال محتوای غیر از عکس
    bot.send_message(msg.chat.id, "لطفاً فقط یک عکس از رسید خود ارسال کنید ❗️")


## pic_receipt is sended as pic and make reserve in db
@bot.message_handler(state=user_State.get_rec,content_types=['photo'])
def reserve_section_enter_name_first_time(msg : Message):
    with bot.retrieve_data(user_id=msg.chat.id , chat_id=msg.chat.id) as data:
        services =data['services']
        total_time=data['total_time']
        total_price=data['total_price']
        date=data['date']
        time=data['time']
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    markup=InlineKeyboardMarkup()
    approve_btn=InlineKeyboardButton(text="ثبت رزرو ✅",callback_data="approve_btn")
    deny_btn=InlineKeyboardButton(text="رد کردن رزرو ❌",callback_data="deny_btn")
    markup.add(approve_btn)
    markup.add(deny_btn)

    user_id=msg.from_user.id
    result,reserve_id=db_make_reserve_transaction(user_id=user_id,services=services,duration=total_time,price=total_price,date=date,start_time=time)

    if not result:
        text=text_transaction_problem
        bot.send_message(msg.chat.id,text=text)
        return 
    
    
    
    #msg to admin (the main one )
    main_admin=int(db_admin_get_main_admin())
    forwarded_msg=bot.forward_message(chat_id=main_admin,from_chat_id=msg.chat.id,message_id=msg.message_id)
    # end_time=add_times(time1=f"{time}",time2=f"{total_time}")
    per_date=convertDateToPersianCalendar(date=date)
    start_time_obj = datetime.strptime(time, "%H:%M:%S")
    duration_parts = list(map(int, total_time.split(':')))
    duration_obj = timedelta(hours=duration_parts[0], minutes=duration_parts[1], seconds=duration_parts[2])
    end_time_obj = start_time_obj + duration_obj
    end_time = end_time_obj.strftime("%H:%M:%S")
    text=make_reservation_info_text_for_user(date=per_date,start_time=time,price=total_price,end_time=end_time,services=services, )
    user_id =msg.from_user.id
    data_user =db_Users_Find_User_By_Id(user_id=user_id)
    text_user_info = text_cleaner_info_user(data=data_user)
    text=f"{text} \n\n{text_user_info}\n reserve_id={reserve_id} \n user_id={user_id}" #! do not change it
    bot.send_message(chat_id=main_admin,text=text,reply_to_message_id=forwarded_msg.message_id,disable_notification=True,reply_markup=markup)
    bot.delete_state(user_id= msg.from_user.id,chat_id=msg.chat.id)

    #msg to user
    text=text_wait_for_approve
    bot.send_message(msg.chat.id,text=text)


### accept btn
@bot.callback_query_handler(func=lambda call: call.data ==("approve_btn"))
def callback_query(call:CallbackQuery):
    markup=InlineKeyboardMarkup()
    btn=InlineKeyboardButton(text="این تراکنش تایید شد ✅",callback_data="!?!?!?!")
    markup.add(btn)
    info_text=call.message.text
    # approve transaction
    reserve_id,user_id=extract_reserveId_and_userId(info_text)
    result=db_Reserve_Update_Approved_Of_Reserve(reserve_id=reserve_id,approved=True)

    if not result:# to admin
        text=text_problem_with_approve_or_deny
        bot.send_message(call.message.chat.id,text=text)
        return 

    #send approve msg to user
    bot.send_message(chat_id=user_id,text=reserve_is_approved)

    #admin edit message
    text=info_text
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.message_id,text=text,reply_markup=markup)


## deny btn 
@bot.callback_query_handler(func=lambda call: call.data ==("deny_btn"))
def callback_query(call:CallbackQuery):
    info_text=call.message.text
    reserve_id,user_id=extract_reserveId_and_userId(info_text)
    
    markup=InlineKeyboardMarkup()
    btn=InlineKeyboardButton(text="این تراکنش رد شد ❌",callback_data="!?!?!?!")
    btn2=InlineKeyboardButton(text="علت رد کردن تراکنش را بنویسید",callback_data=f"deny_message_to_{user_id}")
    markup.add(btn)
    markup.add(btn2)

    # remove reserve from db 
    result=delete_reservation(reserve_id)

    if not result:
        text=text_problem_with_approve_or_deny
        bot.send_message(call.message.chat.id,text=text)
        return 
  
    #send deny msg to user
    bot.send_message(chat_id=user_id,text=reserve_is_denied)

    #admin edit message
    text=info_text
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.message_id,text=text,reply_markup=markup)

#deny msg reason
@bot.callback_query_handler(func=lambda call: call.data.startswith("deny_message_to_"))
def deny_msg(call : CallbackQuery):
    user_id=int(call.data.split('_')[3])
    msg=f"{call.message.text}"

    text=text_deny_reason
    bot.send_message(chat_id=call.message.chat.id,text=text)
    bot.set_state(user_id=call.message.chat.id,state=admin_State.send_deny_reason,chat_id=call.message.chat.id)

    with bot.retrieve_data(call.message.chat.id, call.message.chat.id) as data:
        data['user_id'] = user_id
 

 #send deny reason to user
@bot.message_handler(state=admin_State.send_deny_reason)
def deny_reason(msg : Message):
    with bot.retrieve_data(msg.chat.id, msg.chat.id) as data:
        # user_id = int(data.get('user_id'))
        user_id = int( data['user_id'])

    deny_reason_msg=msg.text
    bot.send_message(chat_id=user_id,text=f"علت رد شدن تراکنش شما : \n {deny_reason_msg}")
    bot.send_message(chat_id=msg.from_user.id,text="پیام شما برای کاربر ارسال شد ✅")
    bot.delete_state(user_id= msg.from_user.id,chat_id=msg.chat.id)

#### activation_user
def activation_user(msg : Message) :
        bot.send_message(chat_id=msg.from_user.id,text=text_enter_name)
        bot.set_state(user_id=msg.chat.id,state=user_State.state_info_enter_name,chat_id=msg.chat.id)


### Enter name for first time after press 'reserve time'
@bot.message_handler(state=user_State.state_info_enter_name)
def reserve_section_enter_name_first_time(msg : Message):
    db_Users_Update_Name_User(user_id=msg.from_user.id ,name=msg.text)
    bot.send_message(chat_id=msg.from_user.id,text=text_enter_phone_number)
    bot.set_state(user_id=msg.chat.id,state=user_State.state_info_enter_phone_number,chat_id=msg.chat.id)

###Enter phone_number for first time after press 'reserve time'
@bot.message_handler(state=user_State.state_info_enter_phone_number)
def reserve_section_state_enter_phone_number(msg : Message):

    pattern =r'^09\d{9}$'
    match = re.match(pattern, msg.text)
    if not match:
        bot.send_message(chat_id=msg.chat.id, text=text_update_phone_number_error)
        return 
    db_Users_Update_Phone_Number_User(user_id=msg.from_user.id ,phone_number=msg.text)
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    bot.send_message(chat_id=msg.from_user.id,text=text_complete_enter_info)


####################################################################### Account Info Section
@bot.message_handler(func= lambda m:m.text == mark_text_account_info)
def account_info(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id) 
    if not bot_is_enable:
        bot_is_disable(user_id=msg.from_user.id) 
        return
    name = db_Users_Get_Name_User(msg.from_user.id)
    if name == 'empty' : 
            activation_user(msg=msg)
    else :
        user_id=db_Users_Find_User_By_Id(msg.from_user.id)
        text = text_cleaner_info_user(user_id)
        markup = markup_generate_account_info(msg.from_user.id)
        bot.send_message(chat_id=msg.chat.id,text=text, reply_markup=markup)



### markup update name
@bot.callback_query_handler(func= lambda m:m.data.startswith("updateNameUser_"))
def updateNameUser(call:CallbackQuery):
    user_id=call.data.split('_')[1]
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_enter_name)
    bot.set_state(user_id=call.from_user.id,state=user_State.state_info_update_name)
    with bot.retrieve_data(call.message.chat.id, call.message.chat.id) as data:
        data['user_id'] = user_id
### state update name
@bot.message_handler(state=user_State.state_info_update_name)
def account_info_state_update_name(msg : Message):
    with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        user_id = int(data['user_id'])

        #prevent for conflict insert support text
        if msg.text == 'پشتیبانی 💬':
            bot.send_message(chat_id=msg.chat.id, text=text_enter_name)
            return
        
        db_Users_Update_Name_User(user_id=user_id , name=msg.text )
        markup=InlineKeyboardMarkup()
        markup = markup_generate_account_info(user_id=user_id)
        data_user=db_Users_Find_User_By_Id(msg.from_user.id)
        text =  f'نام شما تغییر کرد\n\n'+text_cleaner_info_user(data_user)
        bot.send_message(chat_id=user_id,text=text,reply_markup=markup)
        bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    

### markup update phone_number
@bot.callback_query_handler(func= lambda m:m.data.startswith("updatePhoneNumberUser_"))
def updateNameUser(call:CallbackQuery):
    user_id=call.data.split('_')[1]
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text=text_enter_phone_number)
    bot.set_state(user_id=call.from_user.id,state=user_State.state_info_update_phone_number)
    with bot.retrieve_data(call.message.chat.id, call.message.chat.id) as data:
        data['user_id'] = user_id


### state update phone_number
@bot.message_handler(state=user_State.state_info_update_phone_number)
def account_info_state_update_name(msg : Message):
    with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        user_id = int(data['user_id'])
        #prevent for conflict insert support text
        if msg.text == 'پشتیبانی 💬':
            bot.send_message(chat_id=msg.chat.id, text=text_update_phone_number_error)
            return
        pattern =r'^09\d{9}$'
        match = re.match(pattern, msg.text)
        if not match:
            bot.send_message(chat_id=msg.chat.id, text=text_update_phone_number_error)
            return 
        db_Users_Update_Phone_Number_User(user_id=user_id , phone_number=msg.text )
        markup=InlineKeyboardMarkup()
        markup = markup_generate_account_info(user_id=user_id)
        data_user=db_Users_Find_User_By_Id(msg.from_user.id)
        text = f'شماره تماس شما تغییر کرد\n\n'+ text_cleaner_info_user(data_user)
        bot.send_message(chat_id=user_id,text=text,reply_markup=markup)
        bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
####################################################################### Support Section
@bot.message_handler(func= lambda m:m.text == mark_text_support)
def text_to_support(msg : Message):
    bot.delete_state(user_id=msg.from_user.id,chat_id=msg.chat.id)
    if not bot_is_enable:
        bot_is_disable(user_id=msg.from_user.id) 
        return
    main_admin=db_admin_get_main_admin()
    text=f"""<a href='tg://user?id={main_admin}'> برا ارتباط با پشتیبان لطفا روی این متن کلیک کنید </a>"""
    bot.send_message(msg.chat.id, text=text)
#######################################################################
def startMessageToAdmin(enable=True,disable_notification=True):
    if not enable:
        return False

    text=f'{msg_restart} \n 🚫{get_current_datetime()}🚫'

    #get last log    
    latest_log_file = get_latest_log_file()
    admin_list=db_admin_get_all()
    if admin_list is None or len (admin_list)<1 :
        logging.error("send start msg = admin list is none ")
        return False
    for admin in admin_list:#send for all admins
        if latest_log_file:
            last_3_errors=get_last_errors(latest_log_file)
            error_message = "\n".join(last_3_errors)
            with open(latest_log_file, 'rb') as log_file:
                bot.send_document(admin[0], log_file,caption=f"{text}\n{error_message}",disable_notification=disable_notification)
            logging.info(f"send last log to admin [{admin[0]}] : {latest_log_file}")
        else:
            logging.info("there is no log file to show")
            bot.send_message(chat_id=admin,text=f"{text}\n ⛔️فایل log وجود ندارد⛔️",disable_notification=disable_notification)

######################################################################## bot is disable
def toggle_bot_status():
    global bot_is_enable
    bot_is_enable = not bot_is_enable
######################################################################## bot is disable
def bot_is_disable(user_id):
    bot.send_message(chat_id=user_id,text=text_bot_is_disable)
########################################################################! END :)
if __name__ == "__main__":
    # log init
    log_filename = f"./logs/output_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    logging.basicConfig(filename=log_filename,
                        level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.info("Logging is running")
    remove_old_logs()
    
    try:
        # db setting
        createTables()
        insert_basic_setting()
        bot_is_enable = True if db_bot_setting_get_value_by_name(name="bot_is_enable") == "1" else False
        startMessageToAdmin()
        
        # bot setting
        bot.add_custom_filter(custom_filters.StateFilter(bot))
        bot.polling()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise  # Raise the exception again to crash the program
