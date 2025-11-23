# spaceinvador.py  - Full updated version
import pygame
import random
import sys
import time
import os

# ---------------------------
# AUDIO & PYGAME INITIALIZE
# ---------------------------
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
try:
    pygame.mixer.init()
except Exception as e:
    print("Warning: pygame.mixer.init() failed:", e)

def safe_load_sound(path):
    try:
        snd = pygame.mixer.Sound(path)
        return snd
    except Exception as e:
        # Return dummy object with same interface
        print(f"Sound load failed for '{path}': {e}")
        class DummySound:
            def play(self): pass
            def set_volume(self, v): pass
        return DummySound()

shoot_sound = safe_load_sound("shoot.wav")
explosion_sound = safe_load_sound("explosion.wav")
shoot_sound.set_volume(0.6)
explosion_sound.set_volume(0.6)

# background music optional
try:
    pygame.mixer.music.load("background_music.mpeg")
    pygame.mixer.music.set_volume(0.45)
    pygame.mixer.music.play(-1)
except Exception as e:
    # ignore if missing
    print("Background music not loaded:", e)

# ---------------------------
# SCREEN & CONSTANTS
# ---------------------------
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Space Invader")

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# ---------------------------
# ASSET LOADING (safe)
# ---------------------------
def safe_image_load(path, size=None):
    try:
        im = pygame.image.load(path).convert_alpha()
        if size:
            im = pygame.transform.scale(im, size)
        return im
    except Exception as e:
        # placeholder surface
        print(f"Image '{path}' missing: {e}")
        placeholder = pygame.Surface(size if size else (50, 30), pygame.SRCALPHA)
        placeholder.fill((100, 100, 120))
        return placeholder

player_img = safe_image_load("tank.png", (60, 40))
bullet_img = pygame.Surface((7, 18), pygame.SRCALPHA)
pygame.draw.rect(bullet_img, (255, 255, 0), (0,0,7,18))

enemy_imgs = [
    safe_image_load("alien1.png", (48,36)),
    safe_image_load("alien2.png", (48,36)),
    safe_image_load("alien3.png", (48,36))
]

# explosion frames if provided
explosion_frames = []
i = 1
while True:
    fname = f"explode{i}.png"
    if os.path.exists(fname):
        try:
            img = pygame.image.load(fname).convert_alpha()
            explosion_frames.append(img)
        except Exception as e:
            print("Failed to load", fname, e)
        i += 1
    else:
        break

USE_PROCEDURAL_EXPLOSION = (len(explosion_frames) == 0)

# ---------------------------
# FONTS
# ---------------------------
font = pygame.font.Font(None, 36)
big_font = pygame.font.Font(None, 72)

# ---------------------------
# UI / BUTTON CLASS
# ---------------------------
class Button:
    def __init__(self, x,y,w,h, text):
        self.rect = pygame.Rect(x,y,w,h)
        self.text = text
        self.color = (70,130,180)
        self.highlight = (100,149,237)
    def draw(self, surf):
        mpos = pygame.mouse.get_pos()
        pressed = pygame.mouse.get_pressed()[0]
        if self.rect.collidepoint(mpos):
            pygame.draw.rect(surf, self.highlight, self.rect)
            clicked = pressed
        else:
            pygame.draw.rect(surf, self.color, self.rect)
            clicked = False
        txt = font.render(self.text, True, WHITE)
        surf.blit(txt, txt.get_rect(center=self.rect.center))
        return clicked

# ---------------------------
# GAME CONFIG
# ---------------------------
DIFFICULTIES = {
    "Easy":    {"speed_mul": 0.75, "enemy_count": 6,  "bullet_limit": 7},
    "Medium":  {"speed_mul": 1.0,  "enemy_count": 8,  "bullet_limit": 5},
    "Hard":    {"speed_mul": 1.4,  "enemy_count": 10, "bullet_limit": 4}
}
selected_difficulty = "Medium"

# State variables
game_state = "menu"  # menu, playing, boss, gameover
score = 0
player_hp = 100
lives = 3
bullet_speed = 9
bullets = []
enemies = []
boss = None
boss_active = False
next_boss_score = 20
explosions = []  # list of dicts for explosion animations

HIGHSCORE_FILE = "highscore.txt"

def load_high_score():
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_high_score(val):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(int(val)))
    except Exception as e:
        print("Save high score failed:", e)

high_score = load_high_score()

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def create_enemies(count=None):
    arr = []
    if count is None:
        count = DIFFICULTIES[selected_difficulty]["enemy_count"]
    for _ in range(count):
        im = random.choice(enemy_imgs)
        x = random.randint(0, SCREEN_WIDTH - 48)
        y = random.randint(60, 160)
        base = random.choice([2,3,4])
        speed = base * DIFFICULTIES[selected_difficulty]["speed_mul"]
        arr.append({'img':im, 'x':x, 'y':y, 'speed':speed})
    return arr

def reset_game():
    global player_x, player_y, bullets, enemies, score, player_hp, game_over, boss_active, boss, next_boss_score, lives
    player_x = (SCREEN_WIDTH - 60) // 2
    player_y = SCREEN_HEIGHT - 70
    bullets = []
    enemies = create_enemies()
    score = 0
    player_hp = 100
    lives = 3
    game_over = False
    boss_active = False
    boss = None
    next_boss_score = 20

def is_collision(x1,y1,x2,y2, threshold=32):
    dist = ((x1-x2)**2 + (y1-y2)**2)**0.5
    return dist < threshold

def draw_health_bar(surf, x,y,w,h, hp):
    pct = max(0, min(100, hp)) / 100.0
    bw = int(w * pct)
    if hp > 70:
        col = (0,200,0)
    elif hp > 30:
        col = (240,200,0)
    else:
        col = (200,0,0)
    pygame.draw.rect(surf, (80,80,80), (x,y,w,h))
    pygame.draw.rect(surf, col, (x,y,bw,h))
    pygame.draw.rect(surf, WHITE, (x,y,w,h), 2)
    surf.blit(font.render(f"HP: {int(hp)}", True, WHITE), (x + w + 8, y - 2))

def draw_lives(surf, x,y, count):
    # draw small hearts
    for i in range(count):
        hx = x + i*34
        # two circles + triangle
        r = 7
        pygame.draw.circle(surf, (220,20,60), (hx+8, y+8), r)
        pygame.draw.circle(surf, (220,20,60), (hx+16, y+8), r)
        points = [(hx, y+12), (hx+24, y+12), (hx+12, y+24)]
        pygame.draw.polygon(surf, (220,20,60), points)
        pygame.draw.polygon(surf, WHITE, points, 1)
    surf.blit(font.render(f" x {count}", True, WHITE), (x + count*34 + 8, y))

def spawn_boss():
    global boss
    bimg = random.choice(enemy_imgs)
    bimg = pygame.transform.scale(bimg, (140, 100))
    b = {
        'img': bimg,
        'x': (SCREEN_WIDTH - 140)//2,
        'y': 60,
        'speed': 3 * DIFFICULTIES[selected_difficulty]['speed_mul'],
        'hp': 10 if selected_difficulty=="Easy" else (12 if selected_difficulty=="Medium" else 16)
    }
    boss = b
    return b

# explosion helpers
def add_explosion(x,y):
    if not USE_PROCEDURAL_EXPLOSION:
        explosions.append({'type':'frames', 'x':x, 'y':y, 'frame':0, 'tick':0})
    else:
        explosions.append({'type':'proc', 'x':x, 'y':y, 't':0})

def update_and_draw_explosions(surf):
    for e in explosions[:]:
        if e['type'] == 'frames':
            idx = e['frame']
            if idx < len(explosion_frames):
                img = explosion_frames[idx]
                surf.blit(img, (e['x'], e['y']))
            e['tick'] += 1
            if e['tick'] >= 4:
                e['frame'] += 1
                e['tick'] = 0
            if e['frame'] >= len(explosion_frames):
                explosions.remove(e)
        else:
            t = e['t']
            maxr = 40
            steps = 6
            for k in range(steps):
                r = int((t/6.0) * maxr * (1 + k*0.12))
                alpha = max(0, 220 - t*30 - k*20)
                if r > 0 and alpha > 0:
                    surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                    col = (255, 160 - k*20, 60, int(alpha))
                    pygame.draw.circle(surf, col, (r,r), r)
                    surf.set_colorkey((0,0,0))
                    surf.set_alpha(int(alpha))
                    surf2pos = (e['x'] - r + 16, e['y'] - r + 8)
                    surf.blit(surf, (0,0))
                    screen.blit(surf, surf2pos)
            e['t'] += 1
            if e['t'] > 8:
                explosions.remove(e)

# ---------------------------
# INIT
# ---------------------------
reset_game()
clock = pygame.time.Clock()
running = True

# Menu helper - keyboard driven
def keyboard_menu():
    global selected_difficulty, game_state
    options = ["Start Game", "Instructions", "Difficulty", "Quit"]
    diff_options = list(DIFFICULTIES.keys())
    sel = 0
    in_diff = False
    diff_sel = diff_options.index(selected_difficulty)
    while True:
        # draw menu
        screen.fill((5,5,30))
        title = big_font.render("SPACE INVADERS", True, WHITE)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width())//2, 60))
        for i,opt in enumerate(options):
            col = (255,255,0) if i==sel else WHITE
            screen.blit(font.render(opt, True, col), (320, 220 + i*50))
        screen.blit(font.render(f"Difficulty: {selected_difficulty}", True, WHITE), (300, 420))
        screen.blit(font.render(f"High Score: {high_score}", True, (255,215,0)), (10, SCREEN_HEIGHT-40))
        pygame.display.update()
        # event handling
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:
                    sel = (sel - 1) % len(options)
                elif ev.key == pygame.K_DOWN:
                    sel = (sel + 1) % len(options)
                elif ev.key == pygame.K_RETURN:
                    choice = options[sel]
                    if choice == "Start Game":
                        return "start"
                    elif choice == "Instructions":
                        return "instructions"
                    elif choice == "Difficulty":
                        # open difficulty sub-menu
                        while True:
                            screen.fill((10,10,40))
                            screen.blit(big_font.render("Select Difficulty", True, WHITE), ((SCREEN_WIDTH - 380)//2, 80))
                            for j,d in enumerate(diff_options):
                                col = (255,255,0) if j==diff_sel else WHITE
                                screen.blit(font.render(d, True, col), (SCREEN_WIDTH//2 - 60, 200 + j*50))
                            screen.blit(font.render("Enter=select, Esc=back", True, WHITE), (SCREEN_WIDTH//2 - 120, 420))
                            pygame.display.update()
                            for ev2 in pygame.event.get():
                                if ev2.type == pygame.QUIT:
                                    pygame.quit(); sys.exit()
                                if ev2.type == pygame.KEYDOWN:
                                    if ev2.key == pygame.K_UP:
                                        diff_sel = (diff_sel -1) % len(diff_options)
                                    elif ev2.key == pygame.K_DOWN:
                                        diff_sel = (diff_sel +1) % len(diff_options)
                                    elif ev2.key == pygame.K_RETURN:
                                        selected_difficulty = diff_options[diff_sel]
                                        return "menu"  # return to menu
                                    elif ev2.key == pygame.K_ESCAPE:
                                        break
                            clock.tick(30)
                    elif choice == "Quit":
                        pygame.quit(); sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                for i,opt in enumerate(options):
                    rect = pygame.Rect(320, 220 + i*50, 200, 36)
                    if rect.collidepoint(mx,my):
                        if opt == "Start Game":
                            return "start"
                        elif opt == "Instructions":
                            return "instructions"
                        elif opt == "Difficulty":
                            keys = list(DIFFICULTIES.keys())
                            idx = keys.index(selected_difficulty)
                            idx = (idx + 1) % len(keys)
                            selected_difficulty = keys[idx]
                        elif opt == "Quit":
                            pygame.quit(); sys.exit()
        clock.tick(30)

# Buttons (visual secondaries)
btn_start = Button((SCREEN_WIDTH-200)//2, 200, 200, 50, "Start Game")
btn_instruct = Button((SCREEN_WIDTH-200)//2, 270, 200, 50, "Instructions")
btn_diff = Button((SCREEN_WIDTH-200)//2, 340, 200, 50, f"Difficulty: {selected_difficulty}")
btn_quit = Button((SCREEN_WIDTH-200)//2, 410, 200, 50, "Quit")
btn_restart = Button((SCREEN_WIDTH-200)//2, SCREEN_HEIGHT//2 + 50, 200, 50, "Restart")

# ---------------------------
# MAIN LOOP
# ---------------------------
while running:
    screen.fill(BLACK)
    # main event handling (non-blocking)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if game_state == "menu":
        action = keyboard_menu()
        if action == "start":
            reset_game()
            game_state = "playing"
        elif action == "instructions":
            # show instructions screen until key or click
            showing = True
            while showing:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        running = False; showing = False
                    if ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                        showing = False
                screen.fill(BLACK)
                inst_title = big_font.render("INSTRUCTIONS", True, WHITE)
                screen.blit(inst_title, ((SCREEN_WIDTH - inst_title.get_width())//2, 40))
                lines = [
                    "Move: Left / Right arrows",
                    "Shoot: SPACE (limited by difficulty)",
                    "HP: If HP reaches 0 → you lose 1 life (HP resets to 100)",
                    "Lives: Lose all lives → Game Over",
                    "Enemies that reach low screen also cost a life",
                    "Boss appears every 20 points; beat it for +10 points",
                    "Use arrow keys + Enter in menu to change difficulty"
                ]
                for i, line in enumerate(lines):
                    screen.blit(font.render(line, True, WHITE), (60, 160 + i*36))
                screen.blit(font.render("Press any key or click to return", True, WHITE), ((SCREEN_WIDTH - 360)//2, 520))
                pygame.display.update()
                clock.tick(30)
        # draw fallback menu visuals
        title = big_font.render("SPACE INVADERS", True, WHITE)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 80))
        btn_diff.text = f"Difficulty: {selected_difficulty}"
        btn_start.draw(screen); btn_instruct.draw(screen); btn_diff.draw(screen); btn_quit.draw(screen)
        screen.blit(font.render(f"High Score: {high_score}", True, (255,215,0)), (10, SCREEN_HEIGHT-40))

    elif game_state == "playing":
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and player_x > 0:
            player_x -= 6
        if keys[pygame.K_RIGHT] and player_x < SCREEN_WIDTH - 60:
            player_x += 6

        # shoot with limit
        bullet_limit = DIFFICULTIES[selected_difficulty]['bullet_limit']
        if keys[pygame.K_SPACE]:
            if len(bullets) < bullet_limit:
                bullets.append([player_x + 28, player_y])
                shoot_sound.play()

        # move bullets
        for b in bullets[:]:
            b[1] -= bullet_speed
            screen.blit(bullet_img, (b[0], b[1]))
            if b[1] < 0:
                bullets.remove(b)

        # spawn boss if condition met
        if (not boss_active) and score >= next_boss_score and score != 0:
            spawn_boss()
            boss_active = True
            game_state = "boss"

        # update enemies list
        for enemy in enemies[:]:
            enemy['x'] += enemy['speed']
            if enemy['x'] <= 0 or enemy['x'] >= SCREEN_WIDTH - 48:
                enemy['speed'] = -enemy['speed']
                enemy['y'] += 40
            screen.blit(enemy['img'], (enemy['x'], enemy['y']))

            # if enemy falls too low, cost a life and remove
            if enemy['y'] > SCREEN_HEIGHT - 120:
                try:
                    enemies.remove(enemy)
                except ValueError:
                    pass
                lives -= 1
                add_explosion(enemy['x'], enemy['y'])
                if lives <= 0:
                    game_state = "gameover"
                continue

            # bullets vs enemy
            for b in bullets[:]:
                if is_collision(enemy['x'], enemy['y'], b[0], b[1]):
                    if b in bullets:
                        bullets.remove(b)
                    explosion_sound.play()
                    add_explosion(enemy['x'], enemy['y'])
                    # respawn enemy
                    enemy['x'] = random.randint(0, SCREEN_WIDTH - 48)
                    enemy['y'] = random.randint(60, 160)
                    base = random.choice([2,3,4])
                    enemy['speed'] = base * DIFFICULTIES[selected_difficulty]['speed_mul']
                    enemy['img'] = random.choice(enemy_imgs)
                    score += 1

            # enemy vs player collision - damage HP
            if is_collision(enemy['x'] + 24, enemy['y'] + 18, player_x + 30, player_y + 20, threshold=40):
                player_hp -= 30
                explosion_sound.play()
                add_explosion(enemy['x'], enemy['y'])
                # respawn enemy
                enemy['x'] = random.randint(0, SCREEN_WIDTH - 48)
                enemy['y'] = random.randint(60, 160)
                if player_hp <= 0:
                    lives -= 1
                    player_hp = 100
                    if lives <= 0:
                        game_state = "gameover"

        # draw player
        screen.blit(player_img, (player_x, player_y))
        # HUD
        screen.blit(font.render(f"Score: {score}", True, WHITE), (10,10))
        draw_health_bar(screen, 160, 10, 220, 20, player_hp)
        draw_lives(screen, 10, 50, lives)
        update_and_draw_explosions(screen)

        if len(enemies) == 0:
            enemies = create_enemies()

    elif game_state == "boss":
        # safety: ensure boss exists
        if boss is None:
            # fallback: spawn if missing
            spawn_boss()
            boss_active = True

        # boss movement
        boss['x'] += boss['speed']
        if boss['x'] <= 0 or boss['x'] >= SCREEN_WIDTH - boss['img'].get_width():
            boss['speed'] = -boss['speed']

        # draw boss
        screen.blit(boss['img'], (boss['x'], boss['y']))
        # draw boss HP bar
        maxhp = 16 if selected_difficulty=="Hard" else (12 if selected_difficulty=="Medium" else 10)
        pygame.draw.rect(screen, (100,100,100), (SCREEN_WIDTH//2 - 100, boss['y'] - 20, 200, 12))
        pygame.draw.rect(screen, (200,0,0), (SCREEN_WIDTH//2 - 100, boss['y'] - 20, int(200 * (boss['hp'] / maxhp)), 12))
        pygame.draw.rect(screen, WHITE, (SCREEN_WIDTH//2 - 100, boss['y'] - 20, 200, 12), 2)

        # player movement during boss
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and player_x > 0: player_x -= 6
        if keys[pygame.K_RIGHT] and player_x < SCREEN_WIDTH - 60: player_x += 6
        bullet_limit = DIFFICULTIES[selected_difficulty]['bullet_limit']
        if keys[pygame.K_SPACE]:
            if len(bullets) < bullet_limit:
                bullets.append([player_x + 28, player_y])
                shoot_sound.play()

        # bullets move and draw
        for b in bullets[:]:
            b[1] -= bullet_speed
            screen.blit(bullet_img, (b[0], b[1]))
            if b[1] < 0: bullets.remove(b)

        # bullets vs boss - safe check
        if boss is not None:
            for b in bullets[:]:
                if is_collision(boss['x'] + boss['img'].get_width()/2, boss['y'] + boss['img'].get_height()/2, b[0], b[1], threshold=70):
                    if b in bullets: bullets.remove(b)
                    explosion_sound.play()
                    add_explosion(boss['x'], boss['y'])
                    boss['hp'] -= 1
                    if boss['hp'] <= 0:
                        explosion_sound.play()
                        add_explosion(boss['x'], boss['y'])
                        score += 10
                        boss = None
                        boss_active = False
                        next_boss_score += 20
                        enemies = create_enemies()
                        game_state = "playing"
                        break

        # boss hits player - safe check
        if boss is not None:
            if is_collision(boss['x'] + boss['img'].get_width()/2, boss['y'] + boss['img'].get_height()/2, player_x + 30, player_y + 20, threshold=80):
                player_hp -= 40
                explosion_sound.play()
                add_explosion(boss['x'], boss['y'])
                if player_hp <= 0:
                    lives -= 1
                    player_hp = 100
                    if lives <= 0:
                        game_state = "gameover"
                    else:
                        boss = None
                        boss_active = False
                        enemies = create_enemies()
                        game_state = "playing"

        # draw player and HUD
        screen.blit(player_img, (player_x, player_y))
        screen.blit(font.render(f"Score: {score}", True, WHITE), (10,10))
        draw_health_bar(screen, 160, 10, 220, 20, player_hp)
        draw_lives(screen, 10, 50, lives)
        update_and_draw_explosions(screen)

    elif game_state == "gameover":
        # update high score
        if score > high_score:
            save_high_score(score)
            high_score = score
        screen.blit(big_font.render("GAME OVER", True, WHITE), ((SCREEN_WIDTH - 350)//2, SCREEN_HEIGHT//2 - 80))
        screen.blit(font.render(f"Final Score: {score}", True, WHITE), ((SCREEN_WIDTH - 200)//2, SCREEN_HEIGHT//2 - 10))
        screen.blit(font.render(f"High Score: {max(score, high_score)}", True, (255,215,0)), ((SCREEN_WIDTH - 220)//2, SCREEN_HEIGHT//2 + 30))
        if btn_restart.draw(screen):
            game_state = "menu"

    pygame.display.update()
    clock.tick(60)

# Save highscore on exit
if score > high_score:
    save_high_score(score)

pygame.quit()
sys.exit()
