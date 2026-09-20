"""委托任务弹窗；数值与结算仍由 commissions.py / engine.py 管理。"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

import commissions as C
import engine
from data import SKILLS
from i18n import get_country_name, get_lang, t
import ui_v4 as U
from ui_modal import make_button, make_modal, modal_header
from ui_shared import COLORS
from ui_v4 import hline, mk_label


def _name_of(com) -> str:
    return com.name_zh if get_lang() == 'zh' else com.name_en


def _goal_text(com) -> str:
    if com.goal == 'pen':
        return t('com_goal_pen').format(
            country=get_country_name(com.target_country) or com.target_country,
            target=com.target_value)
    if com.goal == 'downloads':
        return t('com_goal_downloads').format(target=com.target_value)
    if com.goal == 'compute':
        return t('com_goal_compute').format(target=com.target_value)
    if com.goal == 'skill':
        sk = SKILLS.get(com.skill_id)
        return t('com_goal_skill').format(
            skill=(sk.name if sk else (com.skill_id or '?')),
            target=int(com.target_value))
    if com.goal == 'stealth':
        return t('com_goal_stealth').format(target=com.target_value)
    return t('com_goal_unlock').format(target=com.target_value)


def _progress(com) -> str:
    ctx = engine.build_commission_ctx(com)
    if com.goal == 'pen':
        return f"{ctx['target_pen_delta']:.1f}/{com.target_value:.1f}"
    if com.goal == 'downloads':
        return f"{ctx['downloads_delta']:.1f}/{com.target_value:.1f}M"
    if com.goal == 'compute':
        return f"{ctx['compute_earned_delta']:.0f}/{com.target_value:.0f}"
    if com.goal == 'skill':
        uses = ctx['skill_uses_delta'].get(com.skill_id, 0)
        return f"{uses}/{int(com.target_value)}"
    if com.goal == 'stealth':
        return f"{t('com_sus_short')} {ctx['suspicion']:.0f}/{com.target_value:.0f}"
    return f"{ctx['unlocked_delta']:.0f}/1"


class CommissionMixin:
    """左侧任务入口及委托列表、详情弹窗。"""

    def show_commission_list(self) -> None:
        p = engine.player
        if p is None:
            return
        items = list(p.commissions)
        content = BoxLayout(orientation='vertical', spacing=0, padding=0)
        content.add_widget(modal_header(
            U.SYM['tasks'], t('com_task_title'),
            chips=[(str(len(items)), 'cost' if items else 'plain')]))
        content.add_widget(hline())
        rows = BoxLayout(orientation='vertical', spacing=8, padding=(12, 10),
                         size_hint_y=None)
        rows.bind(minimum_height=rows.setter('height'))
        if not items:
            rows.add_widget(mk_label(t('com_task_empty'), font_size=U.FS_BODY,
                                      color=COLORS['text_mute'],
                                      size_hint_y=None, height=64))
        for com in items:
            offered = com.status == 'offered'
            tag = t('com_offer_tag') if offered else t('com_active_tag')
            if offered:
                detail = (f"{t('com_reward_est')} "
                          f"~{C.compute_reward(p.tick_count, com.reward_mult):.0f}"
                          f"{t('com_reward_unit')}")
            else:
                left = max((com.deadline_tick or p.tick_count) - p.tick_count, 0)
                detail = (f"{_progress(com)} · {t('com_left_short')}"
                          f"{left}{t('com_left_unit')}")
            rows.add_widget(make_button(
                f"{com.icon} {_name_of(com)} · {tag} · {detail}",
                font_size=U.FS_BODY, height=52,
                on_release=lambda *_a, cm=com: self.show_commission_modal(cm)))
        scroll = ScrollView(bar_width=6)
        scroll.add_widget(rows)
        content.add_widget(scroll)
        footer = BoxLayout(size_hint_y=None, height=52, padding=(12, 7))
        footer.add_widget(Widget())
        close_button = make_button(t('com_close'), height=38)
        footer.add_widget(close_button)
        content.add_widget(footer)

        popup = make_modal(content, size_hint=(0.62, 0.72))
        close_button.bind(on_release=popup.dismiss)
        self._commission_list_popup = popup
        self._pause_for_event()

        def _closed(*_args):
            if getattr(self, '_commission_list_popup', None) is popup:
                self._commission_list_popup = None
            self._resume_after_event()

        popup.bind(on_dismiss=_closed)
        popup.open()

    def show_commission_modal(self, com) -> None:
        p = engine.player
        if p is None or com is None:
            return
        offered = com.status == 'offered'
        est = C.compute_reward(p.tick_count, com.reward_mult)
        body = BoxLayout(orientation='vertical', spacing=10, padding=(14, 10))
        tag = t('com_offer_tag') if offered else t('com_active_tag')
        body.add_widget(modal_header(
            com.icon, _name_of(com),
            chips=[(f"{com.template_id} · {tag}", 'cost' if offered else 'on')]))
        body.add_widget(mk_label(_goal_text(com), font_size=U.FS_BODY,
                                 color=COLORS['text'], size_hint_y=None, height=56))
        body.add_widget(hline())
        if com.goal == 'pen' and com.target_country:
            info = (f"{get_country_name(com.target_country) or com.target_country}"
                    f" · {com.window}{t('com_left_unit')}")
        else:
            info = f"{t('com_left_short')}{com.window}{t('com_left_unit')}"
        body.add_widget(mk_label(info, font_size=U.FS_CAP, color=U.MK['dim'],
                                 size_hint_y=None, height=30))
        if offered:
            body.add_widget(mk_label(
                f"{t('com_reward_est')} ~{est:.0f}{t('com_reward_unit')}",
                font_size=U.FS_CAP, color=COLORS['yellow'],
                size_hint_y=None, height=30))
        if com.sus_relief:
            body.add_widget(mk_label(
                t('com_c5_bonus').format(relief=com.sus_relief),
                font_size=U.FS_CAP, color=COLORS['cyan'],
                size_hint_y=None, height=30))
        body.add_widget(BoxLayout())
        buttons = BoxLayout(orientation='horizontal', spacing=10,
                            size_hint_y=None, height=52)
        if offered:
            buttons.add_widget(make_button(
                t('com_accept'), on_release=lambda *_a: self._accept_commission(com.uid)))
            buttons.add_widget(make_button(
                t('com_decline'), on_release=lambda *_a: self._decline_commission(com.uid)))
        else:
            buttons.add_widget(make_button(t('com_close')))
        body.add_widget(buttons)

        popup = make_modal(body, size_hint=(0.5, 0.62))
        for button in buttons.children:
            button.bind(on_release=popup.dismiss)
        self._commission_detail_popup = popup
        self._pause_for_event()

        def _closed(*_args):
            if getattr(self, '_commission_detail_popup', None) is popup:
                self._commission_detail_popup = None
            self._resume_after_event()

        popup.bind(on_dismiss=_closed)
        popup.open()

    def _accept_commission(self, uid: int) -> None:
        if engine.accept_commission(uid):
            com = next((c for c in engine.player.commissions if c.uid == uid), None)
            if com is not None:
                self._notify(f"{t('com_active_tag')}: {_name_of(com)}")

    def _decline_commission(self, uid: int) -> None:
        com = next((c for c in engine.player.commissions
                    if c.uid == uid and c.status == 'offered'), None)
        name = _name_of(com) if com is not None else '?'
        if engine.decline_commission(uid):
            self._notify(f"{t('com_declined_log')}: {name}")
