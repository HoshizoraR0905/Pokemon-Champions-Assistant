"""Literal UI statements of termination; no inferred timers or mechanics."""
import re


def ending(text):
    text = re.sub(r'\s+', '', text).rstrip('！!。.')
    weather = {'雨停了': 'rain', '雨停止了': 'rain', '下雨停止了': 'rain',
               '雪停了': 'snow', '下雪停止了': 'snow', '沙暴平息了': 'sandstorm',
               '沙暴停止了': 'sandstorm', '阳光不再强烈了': 'sun'}
    if text in weather:
        return 'weather_change', 'field', dict(weather=weather[text], change='end')
    terrain = {'脚下的青草消失了': 'grassy', '脚下的电流消失了': 'electric',
               '脚下的雾气消失了': 'misty', '脚下的奇妙感觉消失了': 'psychic'}
    if text in terrain:
        return 'terrain_change', 'field', dict(terrain=terrain[text], change='end')
    if text in {'扭曲的时空恢复了', '扭曲的时空复原了', '时空恢复正常了'}:
        return 'trick_room_change', 'field', dict(change='end')
    match = re.fullmatch(r'(我方|对手|对方)的?(顺风|反射壁|光墙|极光幕)(停止了|停息了|消失了|结束了)', text)
    if match:
        return 'side_condition_change', 'self' if match[1] == '我方' else 'opponent', dict(
            condition={'顺风': 'tailwind', '反射壁': 'reflect', '光墙': 'light_screen',
                       '极光幕': 'aurora_veil'}[match[2]], change='end')
    return None
