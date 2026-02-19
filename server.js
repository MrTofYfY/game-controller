// server.js
const TelegramBot = require('node-telegram-bot-api');
const express = require('express');

const TOKEN = '8250272065:AAEF3jXFAm90xnmnb8If7VLFvLR1ztBwIeA';
const ADMIN_ID = 6103855234; // Ваш Telegram ID

const bot = new TelegramBot(TOKEN, { polling: true });
const app = express();
app.use(express.json());

// Очередь команд для Roblox
let commandQueue = [];

// Обработка команд от Telegram
bot.on('message', (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    const text = msg.text;

    // Проверка прав администратора
    if (userId !== ADMIN_ID) {
        bot.sendMessage(chatId, '❌ У вас нет прав для использования этого бота.');
        return;
    }

    if (!text || !text.startsWith('/')) return;

    const parts = text.split(' ');
    const command = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');

    // Список команд
    if (command === '/start' || command === '/help') {
        bot.sendMessage(chatId, 
            `🎮 *Roblox Server Manager*\n\n` +
            `📢 */announce [текст]* - Глобальное сообщение\n` +
            `👢 */kickall [причина]* - Кикнуть всех игроков\n` +
            `💨 */speed [значение]* - Изменить скорость (default: 16)\n` +
            `🌍 */gravity [значение]* - Изменить гравитацию (default: 196)\n` +
            `🔄 */resetspeed* - Сбросить скорость\n` +
            `🔄 */resetgravity* - Сбросить гравитацию\n` +
            `👥 */players* - Список игроков\n` +
            `🔧 */shutdown* - Выключить сервер\n` +
            `📊 */status* - Статус сервера`,
            { parse_mode: 'Markdown' }
        );
        return;
    }

    let commandData = null;

    switch (command) {
        case '/announce':
            if (!args) { bot.sendMessage(chatId, '❌ Укажите текст сообщения!'); return; }
            commandData = { type: 'announce', message: args };
            bot.sendMessage(chatId, `✅ Отправлено глобальное сообщение: "${args}"`);
            break;

        case '/kickall':
            commandData = { type: 'kickall', reason: args || 'Kicked by admin' };
            bot.sendMessage(chatId, `✅ Все игроки будут кикнуты. Причина: "${args || 'Kicked by admin'}"`);
            break;

        case '/speed':
            const speed = parseFloat(args);
            if (isNaN(speed) || speed < 0 || speed > 1000) {
                bot.sendMessage(chatId, '❌ Укажите корректное значение скорости (0-1000)!');
                return;
            }
            commandData = { type: 'speed', value: speed };
            bot.sendMessage(chatId, `✅ Скорость изменена на ${speed}`);
            break;

        case '/gravity':
            const gravity = parseFloat(args);
            if (isNaN(gravity) || gravity < 0 || gravity > 1000) {
                bot.sendMessage(chatId, '❌ Укажите корректное значение гравитации (0-1000)!');
                return;
            }
            commandData = { type: 'gravity', value: gravity };
            bot.sendMessage(chatId, `✅ Гравитация изменена на ${gravity}`);
            break;

        case '/resetspeed':
            commandData = { type: 'speed', value: 16 };
            bot.sendMessage(chatId, '✅ Скорость сброшена до 16');
            break;

        case '/resetgravity':
            commandData = { type: 'gravity', value: 196 };
            bot.sendMessage(chatId, '✅ Гравитация сброшена до 196');
            break;

        case '/players':
            commandData = { type: 'getplayers' };
            bot.sendMessage(chatId, '📋 Запрос списка игроков отправлен...');
            break;

        case '/shutdown':
            commandData = { type: 'shutdown' };
            bot.sendMessage(chatId, '🔴 Сервер будет выключен!');
            break;

        case '/status':
            commandData = { type: 'getstatus' };
            bot.sendMessage(chatId, '📊 Запрос статуса отправлен...');
            break;

        default:
            bot.sendMessage(chatId, '❓ Неизвестная команда. Используйте /help');
            return;
    }

    if (commandData) {
        commandData.id = Date.now();
        commandData.chatId = chatId;
        commandQueue.push(commandData);
        console.log('Command added:', commandData);
    }
});

// API для Roblox - получить команды
app.get('/get-commands', (req, res) => {
    const secret = req.headers['x-secret-key'];
    if (secret !== '11448888Guy') {
        return res.status(403).json({ error: 'Forbidden' });
    }
    res.json({ commands: commandQueue });
    commandQueue = []; // Очищаем после отправки
});

// API для Roblox - отправить данные обратно (список игроков, статус)
app.post('/send-data', (req, res) => {
    const secret = req.headers['x-secret-key'];
    if (secret !== 'ВАШ_СЕКРЕТНЫЙ_КЛЮЧ') {
        return res.status(403).json({ error: 'Forbidden' });
    }

    const { chatId, message } = req.body;
    if (chatId && message) {
        bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    }
    res.json({ success: true });
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
});