from dialog_bot_sdk.bot import DialogBot
from dialog_bot_sdk import interactive_media
from threading import Timer
from pymongo import MongoClient
import grpc
import time

# Utils
client = MongoClient(
    "mongodb://james:alexei1@ds018839.mlab.com:18839/feedback_hackaton", retryWrites=False
)
db = client.feedback_hackaton
users = db.users
guides = db.guides
bot_token = "c06ce466243c8dbd318b097db9813d9200ddd13f"
tokens = db.tokens
events = db.events

# https://github.com/dialogs/chatbot-hackathon - basic things
# https://hackathon.transmit.im/web/#/im/u2108492517 - bot


def add_user_to_admins(id, company):
    users.insert_one({"type": "Office-manager", "id": id, "company": company})


def add_user_to_users(id, company):
    users.insert_one({"type": "User", "id": id, "company": company})


def is_exist(id):
    return False if users.find_one({"id": id}) is None else True


def is_manager(id):
    return True if users.find_one({"id": id})["type"] == "Office-manager" else False


def on_msg(msg, peer):
    bot.messaging.send_message(peer, msg)


def has_token(id, *params):
    message = params[0].message.textMessage.text
    token = tokens.find_one({"token": message})
    if token is None:
        return want_to_create(*params)
    else:
        return whose_token(token, id, params[0].peer)


def whose_token(token, id, peer):
    current_time = int(time.time() * 1000.0)

    if current_time - int(token["time"]) >= 24 * 60 * 60 * 1000:
        delete_token(token)
        return on_msg("Ваш токен", peer)

    if token["type"] == "Office-manager":
        add_user_to_admins(id, token["company"])
        return send_manager_buttons(id, peer)
    else:
        add_user_to_users(id, token["company"])
        return get_guides(id, peer)


def want_to_create(*params):
    bot.messaging.send_message(
        params[0].peer,
        "Хотите создать новую компанию в списке?",
        [
            interactive_media.InteractiveMediaGroup(
                [
                    interactive_media.InteractiveMedia(
                        1,
                        interactive_media.InteractiveMediaButton(
                            "create_company", "Да"
                        ),
                    ),
                    interactive_media.InteractiveMedia(
                        1,
                        interactive_media.InteractiveMediaButton(
                            "not_create_company", "Нет"
                        ),
                    ),
                ]
            )
        ],
    )

def send_manager_buttons(id, peer):
    buttons = [
        interactive_media.InteractiveMediaGroup(
            [
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "add_guide", "Добавить мероприятие"
                    ),
                ),
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "get_user_token", "Получить ключ для приглашения Пользователя"
                    ),
                ),
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "get_admin_token", "Получить ключ для приглашения Офис менеджера"
                    ),
                ),
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "delete_guide", "Удалить мероприятие"
                    ),
                ),
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "get_guides", "Получить все мероприятия"
                    ),
                ),
                interactive_media.InteractiveMedia(
                    1,
                    interactive_media.InteractiveMediaButton(
                        "get_feedbacks", "Получить все отзывы"
                    ),
                ),
            ]
        )
    ]

    bot.messaging.send_message(peer, "Выберите действие", buttons)


def auth(id, peer, *params):
    if is_exist(id):
        send_manager_buttons(id, peer) if is_manager(id) else get_guides(id, peer)
    else:
        has_token(id, *params)


def start_text(peer):
    bot.messaging.send_message(
        peer,
        "Здравствуйте это бот для фидбэков. Чтобы узнать дополнительную информацию напишите /info (вставтьте ключ или напишите сообщение)",
    )


def info_text(peer):
    bot.messaging.send_message(
        peer,
        "Вход в бота может осуществляться через ключ, либо он выполнится автоматически на написание любого сообщения если вы уже зарегистрированны",
    )


# Main fun
def main(*params):
    id = params[0].peer.id
    peer = params[0].peer
    if params[0].message.textMessage.text == "/info":
        info_text(peer)
        return

    if params[0].message.textMessage.text == "/start":
        start_text(peer)
        return

    auth(id, peer, *params)


def render_guides_buttons(peer, guides):
    def make_button(guide):
        return interactive_media.InteractiveMedia(
            1, interactive_media.InteractiveMediaButton(guide["value"], guide["title"])
        )

    buttons = [
        interactive_media.InteractiveMediaGroup([make_button(x) for x in guides])
    ]

    bot.messaging.send_message(peer, "Выберите мероприятие", buttons)


def guide_list(id):
    user = users.find_one({"id": id})
    guide_list_res = list(guides.find({"company": user["company"]}))
    return guide_list_res

def event_list(id):
    user = users.find_one({"id": id})
    guide_list_res = list(events.find({"company": user["company"]}))
    return guide_list_res


def get_guides(id, peer):
    guide_list_data = event_list(id)
    render_guides_buttons(peer, guide_list_data)

def generate_guide_value(company):
    number = len(list(guides.find({"company": company})))
    if number == 0:
        res = company + "1"
    else:
        res = company + str(number + 2)

    return res


def get_company(id):
    res = users.find_one({"id": id})["company"]
    return res


def add_guide(id, company, content, title):
    value = generate_guide_value(company)
    guides.insert_one(
        {"company": company, "value": value, "content": content, "title": title}
    )


def delete_guide(id, peer):
    bot.messaging.send_message(peer, "Напишите название мероприятия который хотите удалить")

    def delete(*params):
        guide_name = params[0].message.textMessage.text
        delete_res = events.find_one_and_delete({"title": guide_name})
        my_guides = guides.find({"title": guide_name})
        for guide in my_guides:
            guides.find_one_and_delete(guide)
        if delete_res is None:
            bot.messaging.send_message(peer, "Мероприятия с таким названием не существует")
        else:
            bot.messaging.send_message(peer, "Меоприятие " + guide_name + " удалено")
        auth(id, peer, *params)
        bot.messaging.on_message(main, on_click)

    bot.messaging.on_message(delete)


def delete_token(token):
    tokens.delete_one({"_id": token["_id"]})


def on_click(*params):
    id = params[0].uid
    value = params[0].value
    peer = bot.users.get_user_peer_by_id(id)
    if value == "create_company":
        bot.messaging.send_message(peer, "Введите имя компании")

        def waiting_of_creating_company(*params):
            company_name = params[0].message.textMessage.text
            exits_companies_dict = list(users.find({"company": company_name}))
            exits_companies_list = [x["company"] for x in exits_companies_dict]

            if company_name in exits_companies_list:
                bot.messaging.send_message(
                    peer, "Компания с таким именем уже существует"
                )
            else:
                users.insert_one(
                    {"type": "Office-manager", "company": company_name, "id": id}
                )
                bot.messaging.send_message(
                    peer, "Компания успешно создана. Теперь вы Офис менеджер"
                )
            auth(id, peer, *params)
            bot.messaging.on_message(main, on_click)

        bot.messaging.on_message(waiting_of_creating_company)

    all_guides = event_list(id)
    guides_values = [x["value"] for x in all_guides]

    if value in guides_values:

        bot.messaging.send_message(peer, "Напишите отзыв по мероприятию")

        def fn_and_go_main(*params):
            content = params[0].message.textMessage.text
            company = get_company(id)
            title = events.find_one({"value":value, "company":company})["title"]

            add_guide(id, company, content, title)
            
            bot.messaging.send_message(peer, "Вы создали отзыв")

            auth(id, peer, *params)

            bot.messaging.on_message(main, on_click)

        bot.messaging.on_message(fn_and_go_main)


    if value == "add_guide":
        bot.messaging.send_message(peer, "Напишите название мероприятие")

        def get_content_and_go_main(*params):
            title = params[0].message.textMessage.text
            company = get_company(id)
            events.insert_one({"company": company, "title": title, "value": generate_guide_value(company)})

            bot.messaging.send_message(peer, "Вы создали мероприятие")
            bot.messaging.on_message(main, on_click)

        bot.messaging.on_message(get_content_and_go_main)

    if value == "delete_guide":
        delete_guide(id, peer)

    if value == "get_user_token":
        current_time = str(int(time.time() * 1000.0))
        token = get_company(id) + current_time
        tokens.insert_one(
            {
                "token": token,
                "type": "user",
                "company": get_company(id),
                "time": current_time,
            }
        )
        bot.messaging.send_message(peer, "Токен для пользователя: " + token)

    if value == "get_admin_token":
        current_time = str(int(time.time() * 1000.0))
        token = get_company(id) + current_time
        tokens.insert_one(
            {
                "token": token,
                "type": "Office-manager",
                "company": get_company(id),
                "time": current_time,
            }
        )
        bot.messaging.send_message(peer, "Токен для ивент менеджера: " + token)

    if value == "get_guides":
        if is_manager(id):
            my_list = event_list(id)
            for event in my_list:
                on_msg("Название мероприятия: "+event["title"], peer)
        else:
            get_guides(id, peer)

    if value == "get_feedbacks":
        feedbacks = guide_list(id)
        for feedback in feedbacks:
            title = feedback['title']
            content = feedback['content']
            on_msg("Название: "+title+"\n Отзыв: " + content, peer)

    if value == "not_create_company":
        bot.messaging.send_message(
            peer,
            "Чтобы пользоваться ботом нужно иметь ключ или создать компанию или быть зарегистрированным",
        )


if __name__ == "__main__":
    bot = DialogBot.get_secure_bot(
        "hackathon-mob.transmit.im",  # bot endpoint (specify different endpoint if you want to connect to your on-premise environment)
        grpc.ssl_channel_credentials(),  # SSL credentials (empty by default!)
        bot_token,
        verbose=False,  # optional parameter, when it's True bot prints info about the called methods, False by default
    )

bot.messaging.on_message(main, on_click)