import requests
import json
from typing import Optional, Dict, List

class XenForoAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'XF-Api-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def get_forums(self) -> Optional[List[Dict]]:
        """Получить список форумов"""
        try:
            response = requests.get(
                f'{self.base_url}/api/forums',
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('forums', [])
            else:
                print(f"Ошибка: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return None
    
    def get_threads(self, forum_id: int) -> Optional[List[Dict]]:
        """Получить список тем в форуме"""
        try:
            response = requests.get(
                f'{self.base_url}/api/forums/{forum_id}/threads',
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('threads', [])
            else:
                print(f"Ошибка: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return None
    
    def create_thread(self, forum_id: int, title: str, message: str) -> bool:
        """Создать новую тему"""
        try:
            data = {
                'node_id': forum_id,
                'title': title,
                'message': message
            }
            response = requests.post(
                f'{self.base_url}/api/threads',
                headers=self.headers,
                json=data
            )
            if response.status_code == 200:
                print("✓ Тема успешно создана!")
                return True
            else:
                print(f"Ошибка создания темы: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"Ошибка: {e}")
            return False
    
    def post_reply(self, thread_id: int, message: str) -> bool:
        """Написать ответ в тему"""
        try:
            data = {
                'message': message
            }
            response = requests.post(
                f'{self.base_url}/api/threads/{thread_id}/posts',
                headers=self.headers,
                json=data
            )
            if response.status_code == 200:
                print("✓ Сообщение успешно отправлено!")
                return True
            else:
                print(f"Ошибка отправки сообщения: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"Ошибка: {e}")
            return False


def print_forums(forums: List[Dict]):
    """Вывести список форумов"""
    print("\n" + "="*60)
    print("СТРУКТУРА ФОРУМА")
    print("="*60)
    for idx, forum in enumerate(forums, 1):
        print(f"{idx}. {forum['title']} (ID: {forum['node_id']})")
        if forum.get('description'):
            print(f"   Описание: {forum['description']}")
    print("="*60)


def print_threads(threads: List[Dict]):
    """Вывести список тем"""
    print("\n" + "="*60)
    print("ТЕМЫ В ФОРУМЕ")
    print("="*60)
    if not threads:
        print("В этом форуме нет тем")
    else:
        for idx, thread in enumerate(threads, 1):
            print(f"{idx}. {thread['title']} (ID: {thread['thread_id']})")
            print(f"   Ответов: {thread.get('reply_count', 0)}")
    print("="*60)


def main():
    print("╔═══════════════════════════════════════════╗")
    print("║   XenForo API - Управление форумом        ║")
    print("╚═══════════════════════════════════════════╝\n")
    
    # Запрос данных для подключения
    base_url = input("Введите URL форума (например, https://forum.example.com): ").strip()
    api_key = input("Введите API ключ: ").strip()
    
    # Инициализация API
    api = XenForoAPI(base_url, api_key)
    
    while True:
        print("\n" + "─"*60)
        print("ГЛАВНОЕ МЕНЮ")
        print("─"*60)
        print("1. Показать структуру форума")
        print("2. Создать новую тему")
        print("3. Ответить в тему")
        print("0. Выход")
        print("─"*60)
        
        choice = input("\nВыберите действие: ").strip()
        
        if choice == '1':
            # Показать форумы
            forums = api.get_forums()
            if forums:
                print_forums(forums)
        
        elif choice == '2':
            # Создать тему
            forums = api.get_forums()
            if forums:
                print_forums(forums)
                
                try:
                    forum_num = int(input("\nВыберите номер форума: "))
                    if 1 <= forum_num <= len(forums):
                        forum = forums[forum_num - 1]
                        
                        title = input("Введите заголовок темы: ").strip()
                        if not title:
                            print("Заголовок не может быть пустым!")
                            continue
                        
                        print("Введите текст сообщения (для завершения введите пустую строку):")
                        message_lines = []
                        while True:
                            line = input()
                            if not line:
                                break
                            message_lines.append(line)
                        
                        message = '\n'.join(message_lines)
                        if not message:
                            print("Сообщение не может быть пустым!")
                            continue
                        
                        api.create_thread(forum['node_id'], title, message)
                    else:
                        print("Неверный номер форума!")
                except ValueError:
                    print("Введите корректное число!")
        
        elif choice == '3':
            # Ответить в тему
            forums = api.get_forums()
            if forums:
                print_forums(forums)
                
                try:
                    forum_num = int(input("\nВыберите номер форума: "))
                    if 1 <= forum_num <= len(forums):
                        forum = forums[forum_num - 1]
                        
                        threads = api.get_threads(forum['node_id'])
                        if threads:
                            print_threads(threads)
                            
                            thread_num = int(input("\nВыберите номер темы: "))
                            if 1 <= thread_num <= len(threads):
                                thread = threads[thread_num - 1]
                                
                                print("Введите текст ответа (для завершения введите пустую строку):")
                                message_lines = []
                                while True:
                                    line = input()
                                    if not line:
                                        break
                                    message_lines.append(line)
                                
                                message = '\n'.join(message_lines)
                                if not message:
                                    print("Сообщение не может быть пустым!")
                                    continue
                                
                                api.post_reply(thread['thread_id'], message)
                            else:
                                print("Неверный номер темы!")
                        else:
                            print("Не удалось получить список тем")
                    else:
                        print("Неверный номер форума!")
                except ValueError:
                    print("Введите корректное число!")
        
        elif choice == '0':
            print("\nДо свидания!")
            break
        
        else:
            print("Неверный выбор! Попробуйте снова.")


if __name__ == "__main__":
    main()
