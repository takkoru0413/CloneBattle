import pygame
import random
import sys
import math
import array
import os
import json

# --- ファイル管理・設定 ---
RANKING_FILE = "ranking.json"
SETTINGS_FILE = "settings.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for k, v in default.items():
                    if k not in data: data[k] = v
                return data
        except: return default
    return default

def save_json(path, data):
    try:
        with open(path, "w") as f: json.dump(data, f, indent=4)
    except: pass

ranking_dict = load_json(RANKING_FILE, {"EASY": [], "NORMAL": [], "HARD": []})
user_settings = load_json(SETTINGS_FILE, {
    "SE": True, 
    "BGM": True,  
    "HARD_UNLOCKED": False,
    "KEYS": {"LEFT": pygame.K_LEFT, "RIGHT": pygame.K_RIGHT, "SHOOT": pygame.K_SPACE, "CLONE": pygame.K_z, "GUARD": pygame.K_c}
})

# --- 定数 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 850
FPS = 60
WHITE, BLACK, GRAY = (255, 255, 255), (0, 0, 0), (100, 100, 100)
GREEN, YELLOW, RED = (50, 255, 50), (255, 255, 0), (255, 50, 50)
GAUGE_BLUE, HP_BAR_COLOR = (50, 150, 255), (0, 255, 100)
GUARD_COLOR = (173, 216, 230)
COLORS = {"RED": RED, "GREEN": GREEN, "BLUE": (50, 100, 255), "YELLOW": YELLOW, "MAGENTA": (255, 0, 255), "CYAN": (0, 255, 255), "ORANGE": (255, 165, 0), "PURPLE": (160, 32, 240)}

PLAYER_CLONE_COST = 40
DIFFICULTIES = {
    "EASY": {"shoot": 0.04, "clone": 0.008},
    "NORMAL": {"shoot": 0.12, "clone": 0.025},
    "HARD": {"shoot": 0.5, "clone": 0.2}
}

COMBO_GAUGE_BONUS = 0.5
STAR_COUNT = 60

# --- エフェクト ---
class DamageText:
    def __init__(self, x, y, text, color):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.life = 40
        self.font = pygame.font.SysFont("impact", 32)
    def update(self):
        self.y -= 1.5
        self.life -= 1
    def draw(self, screen):
        alpha = min(255, self.life * 10)
        s = self.font.render(self.text, True, self.color)
        s.set_alpha(alpha)
        screen.blit(s, (self.x, self.y))

class Spark:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.color = color
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(5, 22)
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.life = random.randint(40, 70)
        self.max_life = self.life
        self.gravity, self.friction = 0.15, 0.92
        self.size = random.randint(3, 6)

    def update(self, slow=1.0):
        self.vx *= (1.0 - (1.0 - self.friction) * slow)
        self.vy *= (1.0 - (1.0 - self.friction) * slow)
        self.vy += self.gravity * slow
        self.x += self.vx * slow
        self.y += self.vy * slow
        self.life -= 1 * slow
        self.current_size = max(1, int(self.size * (self.life / self.max_life)))

    def draw(self, screen, ox, oy):
        if self.life <= 0: return
        alpha = min(255, int(255 * (self.life / self.max_life)))
        s = pygame.Surface((self.current_size * 2, self.current_size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.current_size, self.current_size), self.current_size)
        screen.blit(s, (self.x + ox - self.current_size, self.y + oy - self.current_size))

# --- サウンド ---
class SoundManager:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.mixer.init()
        self.bgm_channel = pygame.mixer.Channel(0)
        self._bgm_data = self._create_bgm_sound()

    def _create_bgm_sound(self):
        notes = [261, 329, 293, 349, 329, 392, 349, 293]
        full_buffer = array.array('h')
        for f in notes:
            s_cnt = int(44100 * 0.25)
            for i in range(s_cnt):
                val = 0.02 * 32767 if math.sin(2.0 * math.pi * f * (i/44100)) > 0 else -0.02 * 32767
                full_buffer.append(int(val))
        return pygame.mixer.Sound(buffer=full_buffer)

    def gen(self, f, d, v=0.1, square=False):
        if not user_settings["SE"]: return None
        s_cnt = int(44100 * d)
        b = array.array('h', [int(v * 32767 * (1 if square and math.sin(2.0*math.pi*f*(i/44100))>0 else (-1 if square else math.sin(2.0*math.pi*f*(i/44100))))) for i in range(s_cnt)])
        return pygame.mixer.Sound(buffer=b)

    def update_bgm(self, force_stop=False):
        should_play = user_settings["BGM"] and not force_stop
        if should_play and not self.bgm_channel.get_busy(): self.bgm_channel.play(self._bgm_data, loops=-1)
        elif not should_play and self.bgm_channel.get_busy(): self.bgm_channel.stop()

    def play_shoot(self): s = self.gen(880, 0.05); s.play() if s else None
    def play_damage(self): s = self.gen(180, 0.15, 0.3); s.play() if s else None
    def play_guard(self): s = self.gen(440, 0.03, 0.05); s.play() if s else None
    def play_clone(self): s = self.gen(660, 0.1); s.play() if s else None
    def play_count(self): s = self.gen(1000, 0.08, 0.07); s.play() if s else None
    def play_start(self): s = self.gen(1500, 0.3, 0.1); s.play() if s else None
    def play_ko(self): s = self.gen(80, 0.6, 0.6, True); s.play() if s else None 
    def play_win(self):
        if not user_settings["SE"]: return
        for f in [523, 659, 783]:
            s = self.gen(f, 0.2); s.play() if s else None; pygame.time.delay(150)
    def play_menu_hover(self): s = self.gen(1200, 0.02, 0.05); s.play() if s else None
    def play_menu_select(self): s = self.gen(1500, 0.1, 0.1); s.play() if s else None

sm = SoundManager()

# --- キャラクター ---
class Character:
    def __init__(self, x, y, color_name, is_upward):
        self.rect = pygame.Rect(x, y, 44, 44)
        self.color = COLORS.get(color_name, WHITE)
        self.is_upward = is_upward
        self.hp, self.ammo, self.gauge = 100, 15, 100.0
        self.bullets, self.clones = [], []
        self.reloading, self.reload_timer, self.shoot_cooldown = False, 0, 0
        self.is_guarding, self.squish_timer, self.is_dead = False, 0, False
        self.hp_shake = 0
        self.speed = 8

    def update(self, target_rect=None, gauge_bonus=0, slow=1.0):
        if self.is_dead: return
        if self.hp_shake > 0: self.hp_shake -= 1
        if self.reloading:
            self.reload_timer -= 1 * slow
            if self.reload_timer <= 0: self.ammo, self.reloading = 15, False
        if self.shoot_cooldown > 0: self.shoot_cooldown -= 1 * slow
        if self.squish_timer > 0: self.squish_timer -= 1 * slow
        if self.is_guarding:
            self.gauge -= 1.5 * slow
            if self.gauge <= 0: self.gauge, self.is_guarding = 0, False
        else: self.gauge = min(100, self.gauge + (1.2 + gauge_bonus) * slow)

        for b in self.bullets[:]:
            b.y += (-16 if self.is_upward else 16) * slow
            if b.bottom < 0 or b.top > SCREEN_HEIGHT: self.bullets.remove(b)
        for c in self.clones[:]:
            rect, vx, vy = c[0], c[1], c[2]
            if target_rect:
                dx, dy = target_rect.centerx - rect.centerx, target_rect.centery - rect.centery
                dist = math.hypot(dx, dy) or 1
                c[1] += (dx/dist)*(1.0 if not self.is_upward else 0.5)*slow
                c[2] += (dy/dist)*(1.0 if not self.is_upward else 0.5)*slow
                mag = math.hypot(c[1], c[2]); limit = 14
                if mag > limit: c[1], c[2] = (c[1]/mag)*limit, (c[2]/mag)*limit
            rect.x += c[1] * slow; rect.y += c[2] * slow
            if not pygame.Rect(-100, -100, SCREEN_WIDTH+200, SCREEN_HEIGHT+200).colliderect(rect): self.clones.remove(c)

    def draw(self, screen, ox=0, oy=0):
        if self.is_dead: return
        r = self.rect.copy()
        if self.squish_timer > 0: r.width += 24; r.height -= 20; r.center = self.rect.center
        r.x += ox; r.y += oy
        pygame.draw.rect(screen, GUARD_COLOR if self.is_guarding else self.color, r)

    def shoot(self):
        if self.ammo > 0 and not self.reloading and self.shoot_cooldown <= 0:
            self.bullets.append(pygame.Rect(self.rect.centerx-5, self.rect.top if self.is_upward else self.rect.bottom, 10, 20))
            self.ammo -= 1; self.shoot_cooldown = 7; sm.play_shoot()
            if self.ammo == 0: self.reloading, self.reload_timer = True, 30

    def launch_clone(self, target_rect):
        cost = PLAYER_CLONE_COST if self.is_upward else 30
        if self.gauge >= cost:
            self.gauge -= cost; sm.play_clone()
            self.clones.append([pygame.Rect(self.rect.x, self.rect.y, 30, 30), 0, 0])

# --- メインクラス ---
class Game:
    def __init__(self):
        pygame.init(); self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock(); self.font = pygame.font.SysFont("msgothic", 22, bold=True)
        self.hp_font = pygame.font.SysFont("impact", 28)
        self.hint_font = pygame.font.SysFont("msgothic", 18, bold=True)
        self.title_font = pygame.font.SysFont("msgothic", 50, bold=True); self.count_font = pygame.font.SysFont("impact", 130)
        self.player_color_name = "GREEN"; self.menu_click_cd = 0; self.hovered_btn = None
        self.bg_stars = [[random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT), random.randint(2, 6)] for _ in range(STAR_COUNT)]

    def draw_btn(self, rect, text, color, active=True, locked=False, hint_text=""):
        mouse = pygame.mouse.get_pos(); hover = rect.collidepoint(mouse)
        if hover and active:
            if self.hovered_btn != rect: sm.play_menu_hover(); self.hovered_btn = rect
        elif self.hovered_btn == rect: self.hovered_btn = None
        
        draw_c = WHITE if hover and active and not locked else color
        if locked: draw_c = GRAY
        
        pygame.draw.rect(self.screen, draw_c, rect, 2)
        txt = self.font.render(text if not locked else "[ LOCKED ]", True, draw_c)
        self.screen.blit(txt, (rect.centerx-txt.get_width()//2, rect.centery-txt.get_height()//2))
        
        if locked and hover and hint_text:
            h_txt = self.hint_font.render(hint_text, True, RED)
            self.screen.blit(h_txt, (rect.centerx-h_txt.get_width()//2, rect.bottom + 10))

        if hover and pygame.mouse.get_pressed()[0] and self.menu_click_cd == 0 and active and not locked:
            sm.play_menu_select(); self.menu_click_cd = 20; return True
        return False

    def menu(self):
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            t = self.title_font.render("CLONE BATTLE", True, WHITE); self.screen.blit(t, (400-t.get_width()//2, 120))
            if self.draw_btn(pygame.Rect(300, 250, 200, 60), "PLAY", GREEN): self.diff_sel()
            if self.draw_btn(pygame.Rect(300, 330, 200, 60), "COLOR", WHITE): self.color_sel()
            if self.draw_btn(pygame.Rect(300, 410, 200, 60), "SETTINGS", WHITE): self.settings_menu()
            if self.draw_btn(pygame.Rect(300, 490, 200, 60), "RANKING", YELLOW): self.show_rank()
            if self.draw_btn(pygame.Rect(300, 570, 200, 60), "QUIT", RED): pygame.quit(); sys.exit()
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            pygame.display.update(); self.clock.tick(FPS)

    def diff_sel(self):
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            if self.draw_btn(pygame.Rect(300, 300, 200, 60), "EASY", GREEN): self.run("EASY"); return
            if self.draw_btn(pygame.Rect(300, 400, 200, 60), "NORMAL", YELLOW): self.run("NORMAL"); return
            if self.draw_btn(pygame.Rect(300, 500, 200, 60), "HARD", RED, 
                            locked=not user_settings["HARD_UNLOCKED"], 
                            hint_text="条件: NORMALでHP75以上残して勝利"): 
                self.run("HARD"); return
            if self.draw_btn(pygame.Rect(300, 650, 200, 50), "BACK", GRAY): return
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            pygame.display.update(); self.clock.tick(FPS)

    def run(self, diff):
        ai_color_choices = [name for name in COLORS.keys() if name != self.player_color_name]
        ai_color_name = random.choice(ai_color_choices)

        p, ai = Character(400, 770, self.player_color_name, True), Character(400, 80, ai_color_name, False)
        start_t, game_on, go_t, play_t = pygame.time.get_ticks(), False, 0, 0.0
        particles, damage_texts, shake, p_combo, slow, finish_t, whiteout = [], [], 0, 0, 1.0, 0, 0
        
        # カウント音管理用
        last_count_val = 4 

        while True:
            sm.update_bgm(finish_t > 0); self.screen.fill(BLACK)
            for s in self.bg_stars:
                s[1] = (s[1] + s[2] * 1.5 * slow) % SCREEN_HEIGHT
                pygame.draw.circle(self.screen, (200, 200, 200), (int(s[0]), int(s[1])), s[2]//2)
            ox, oy = (random.randint(-shake, shake), random.randint(-shake, shake)) if shake > 0 else (0, 0)
            if shake > 0: shake -= 1

            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if game_on and finish_t == 0 and e.type == pygame.KEYDOWN:
                    if e.key == user_settings["KEYS"]["SHOOT"]: p.shoot()
                    if e.key == user_settings["KEYS"]["CLONE"]: p.launch_clone(ai.rect)

            if not game_on:
                cur = 3 - (pygame.time.get_ticks() - start_t) // 1000
                if cur > 0:
                    # ★ 数字が変わった瞬間に音を鳴らす
                    if cur != last_count_val:
                        sm.play_count()
                        last_count_val = cur
                    txt = self.count_font.render(str(cur), True, YELLOW); self.screen.blit(txt, (400-txt.get_width()//2, 330))
                else: 
                    sm.play_start(); game_on, go_t = True, pygame.time.get_ticks()
            else:
                if finish_t == 0:
                    play_t = (pygame.time.get_ticks() - go_t) / 1000.0
                    k = pygame.key.get_pressed()
                    p.is_guarding = k[user_settings["KEYS"]["GUARD"]] and p.gauge > 0
                    spd = (p.speed // 2 if p.is_guarding else p.speed) * slow
                    if k[user_settings["KEYS"]["LEFT"]] and p.rect.left > 0: p.rect.x -= spd
                    if k[user_settings["KEYS"]["RIGHT"]] and p.rect.right < 800: p.rect.x += spd
                    if not ai.is_dead:
                        if ai.rect.centerx < p.rect.centerx: ai.rect.x += ai.speed * slow
                        else: ai.rect.x -= ai.speed * slow
                        if random.random() < DIFFICULTIES[diff]["shoot"]: ai.shoot()
                        if random.random() < DIFFICULTIES[diff]["clone"]: ai.launch_clone(p.rect)

                p.update(ai.rect, p_combo * COMBO_GAUGE_BONUS, slow); ai.update(p.rect, 0, slow)

                if finish_t == 0:
                    for char, other, is_p in [(p, ai, True), (ai, p, False)]:
                        for b in other.bullets[:]:
                            if char.rect.colliderect(b):
                                dmg = 2 if char.is_guarding else 10; char.hp -= dmg; other.bullets.remove(b)
                                damage_texts.append(DamageText(char.rect.x, char.rect.y, f"-{dmg}", WHITE if char.is_guarding else YELLOW))
                                char.hp_shake = 6
                                if not char.is_guarding: sm.play_damage(); shake = 5; p_combo = p_combo+1 if not is_p else p_combo
                                else: sm.play_guard()
                        for cl in other.clones[:]:
                            if char.rect.colliderect(cl[0]):
                                dmg = 5 if char.is_guarding else 25; char.hp -= dmg; other.clones.remove(cl)
                                damage_texts.append(DamageText(char.rect.x, char.rect.y, f"-{dmg}", WHITE if char.is_guarding else RED))
                                char.hp_shake = 12
                                if not char.is_guarding:
                                    sm.play_damage(); shake = 15; char.squish_timer = 10
                                    for _ in range(10): particles.append(Spark(char.rect.centerx, char.rect.centery, char.color))
                                else: sm.play_guard()

                if (ai.hp <= 0 or p.hp <= 0) and finish_t == 0:
                    finish_t, slow, whiteout = 180, 0.2, 255; sm.play_ko()
                    dead = ai if ai.hp <= 0 else p; dead.is_dead = True
                    p.bullets.clear(); ai.bullets.clear(); p.clones.clear(); ai.clones.clear()
                    for _ in range(120): particles.append(Spark(dead.rect.centerx, dead.rect.centery, dead.color))

            for pt in particles[:]:
                pt.update(slow); pt.draw(self.screen, ox, oy)
                if pt.life <= 0: particles.remove(pt)
            for dt in damage_texts[:]:
                dt.update(); dt.draw(self.screen)
                if dt.life <= 0: damage_texts.remove(dt)
            p.draw(self.screen, ox, oy); ai.draw(self.screen, ox, oy)
            for char in [p, ai]:
                for b in char.bullets: pygame.draw.rect(self.screen, YELLOW, (b.x+ox, b.y+oy, b.width, b.height))
                for cl in char.clones: pygame.draw.rect(self.screen, char.color, (cl[0].x+ox, cl[0].y+oy, cl[0].width, cl[0].height), 2)
            
            self.draw_ui(p, ai, play_t, p_combo)

            if finish_t > 0:
                finish_t -= 1
                if whiteout > 0:
                    ws = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)); ws.fill(WHITE); ws.set_alpha(whiteout)
                    self.screen.blit(ws, (0, 0)); whiteout -= 10
                ko_txt = self.count_font.render("K.O.", True, RED); self.screen.blit(ko_txt, (400-ko_txt.get_width()//2, 325))
                if finish_t == 1:
                    if ai.hp <= 0:
                        sm.play_win(); ranking_dict[diff].append(play_t); ranking_dict[diff].sort(); save_json(RANKING_FILE, ranking_dict)
                        if diff == "NORMAL" and p.hp >= 75: 
                            user_settings["HARD_UNLOCKED"] = True
                            save_json(SETTINGS_FILE, user_settings)
                        self.res("WINNER!", GREEN)
                    else: self.res("LOSE...", RED)
                    return
            pygame.display.update(); self.clock.tick(FPS)

    def draw_ui(self, p, a, t, combo):
        pygame.draw.rect(self.screen, RED, (50, 50, 200, 25))
        pygame.draw.rect(self.screen, HP_BAR_COLOR, (50, 50, max(0, a.hp)*2, 25))
        a_hpx = 50 + (random.randint(-2, 2) if a.hp_shake > 0 else 0)
        a_hpy = 15 + (random.randint(-2, 2) if a.hp_shake > 0 else 0)
        a_col = GREEN if a.hp > 50 else (YELLOW if a.hp > 20 else RED)
        self.screen.blit(self.hp_font.render(f"HP: {max(0, int(a.hp))}", True, a_col), (a_hpx, a_hpy))
        self.screen.blit(self.font.render(f"TIME: {t:.2f}s", True, WHITE), (350, 15))
        pygame.draw.rect(self.screen, RED, (550, 770, 200, 25))
        pygame.draw.rect(self.screen, HP_BAR_COLOR, (550, 770, max(0, p.hp)*2, 25))
        p_hpx = 550 + (random.randint(-2, 2) if p.hp_shake > 0 else 0)
        p_hpy = 735 + (random.randint(-2, 2) if p.hp_shake > 0 else 0)
        p_col = GREEN if p.hp > 50 else (YELLOW if p.hp > 20 else RED)
        self.screen.blit(self.hp_font.render(f"HP: {max(0, int(p.hp))}", True, p_col), (p_hpx, p_hpy))
        self.screen.blit(self.font.render(f"AMMO: {p.ammo}", True, WHITE), (550, 805))
        pygame.draw.rect(self.screen, GAUGE_BLUE, (550, 835, p.gauge*2, 10))
        if combo > 1:
            c_txt = pygame.font.SysFont("impact", 40).render(f"{combo} COMBO!", True, YELLOW); self.screen.blit(c_txt, (550, 680))

    def settings_menu(self):
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            if self.draw_btn(pygame.Rect(250, 200, 300, 60), f"BGM: {'ON' if user_settings['BGM'] else 'OFF'}", WHITE):
                user_settings["BGM"] = not user_settings["BGM"]; save_json(SETTINGS_FILE, user_settings)
            if self.draw_btn(pygame.Rect(250, 280, 300, 60), f"SE: {'ON' if user_settings['SE'] else 'OFF'}", WHITE):
                user_settings["SE"] = not user_settings["SE"]; save_json(SETTINGS_FILE, user_settings)
            if self.draw_btn(pygame.Rect(250, 380, 300, 60), "KEY CONFIG", YELLOW): self.key_config_menu()
            if self.draw_btn(pygame.Rect(300, 650, 200, 50), "BACK", GRAY): return
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            pygame.display.update(); self.clock.tick(FPS)

    def key_config_menu(self):
        waiting = None
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            y = 180
            for action, key in user_settings["KEYS"].items():
                label = f"{action}: {pygame.key.name(key).upper()}" if waiting != action else "> PRESS ANY KEY <"
                if self.draw_btn(pygame.Rect(200, y, 400, 50), label, YELLOW if waiting != action else RED): waiting = action
                y += 65
            if self.draw_btn(pygame.Rect(300, 650, 200, 50), "BACK", GRAY): return
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and waiting:
                    user_settings["KEYS"][waiting] = e.key; save_json(SETTINGS_FILE, user_settings); waiting = None
            pygame.display.update(); self.clock.tick(FPS)

    def show_rank(self):
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            for i, d in enumerate(["EASY", "NORMAL", "HARD"]):
                self.screen.blit(self.font.render(f"- {d} -", True, WHITE), (100+i*240, 150))
                for j, r in enumerate(ranking_dict[d]): self.screen.blit(self.font.render(f"{j+1}:{r:.2f}s", True, WHITE), (100+i*240, 200+j*50))
            if self.draw_btn(pygame.Rect(300, 650, 200, 50), "BACK", GRAY): return
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            pygame.display.update(); self.clock.tick(FPS)

    def color_sel(self):
        while True:
            sm.update_bgm(); self.screen.fill(BLACK); self.menu_click_cd = max(0, self.menu_click_cd - 1)
            for i, name in enumerate(COLORS.keys()):
                if self.draw_btn(pygame.Rect(100+(i%2)*350, 150+(i//2)*80, 250, 60), name, COLORS[name]): self.player_color_name = name; return
            if self.draw_btn(pygame.Rect(300, 650, 200, 50), "BACK", GRAY): return
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            pygame.display.update(); self.clock.tick(FPS)

    def res(self, t, c):
        st = pygame.time.get_ticks()
        while pygame.time.get_ticks() - st < 2000:
            self.screen.fill(BLACK); txt = self.title_font.render(t, True, c)
            self.screen.blit(txt, (400-txt.get_width()//2, 400)); pygame.display.update()

if __name__ == "__main__":
    Game().menu()