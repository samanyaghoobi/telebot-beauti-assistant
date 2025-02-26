import logging
import mysql.connector # type: ignore
from mysql.connector import Error

from auth.auth import DB_CONFIG


############################ insert
def db_bot_setting_insert(name:str,value:str):
    sql = f"""INSERT INTO bot_setting (name, value) VALUES (%s, %s);"""
    try:
        with mysql.connector.connect(**DB_CONFIG) as connection:
            if connection.is_connected():
                with connection.cursor() as cursor:
                    cursor.execute(sql, (name, value))
                    connection.commit()
                    logging.info("Record inserted successfully")
                    return True
    except Error as e:
        logging.error(f"Error inserting record: {e}")
        return False
###########################update
def db_bot_setting_update(name, new_value):
    sql = f"""UPDATE bot_setting SET value = %s WHERE name = %s;"""
    try:
        with mysql.connector.connect(**DB_CONFIG) as connection:
            if connection.is_connected():
                with connection.cursor() as cursor:
                    cursor.execute(sql, (new_value, name))
                    connection.commit()
                    logging.info("Record updated successfully")
                    return True
    except Error as e:
        logging.error(f"Error updating record: {e}")
        return False
###############################get
def db_bot_setting_get_value_by_name(name:str):
    sql = f"""SELECT value FROM bot_setting WHERE name = %s;"""
    try:
        with mysql.connector.connect(**DB_CONFIG) as connection:
            if connection.is_connected():
                with connection.cursor() as cursor:
                    cursor.execute(sql, (name,))
                    result = cursor.fetchone()
                    if result:
                        return result[0]
                    else:
                        logging.info("No record found")
                        return None
    except Error as e:
        logging.error(f"Error retrieving record: {e}")
###############################get
def db_bot_setting_get_all():
    sql = f"""SELECT * FROM bot_setting ;"""
    try:
        with mysql.connector.connect(**DB_CONFIG) as connection:
            if connection.is_connected():
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchall()
                    if result:
                        return result
                    else:
                        logging.error("No record found")
                        return None
    except Error as e:
        logging.error(f"Error retrieving record: {e}")
############################### get card info
def db_bot_setting_get_cart_info():
    sql = f"""SELECT * FROM bot_setting WHERE name IN ('cart', 'cart_name', 'cart_bank');"""
    try:
        with mysql.connector.connect(**DB_CONFIG) as connection:
            if connection.is_connected():
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchall()
                    if result:
                        return result
                    else:
                        logging.error("No record found")
                        return None
    except Error as e:
        logging.error(f"Error db_bot_setting_get_cart_info: {e}")
