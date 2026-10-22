import pygame
import random
# -------------------------------
pygame.init()
font = pygame.font.SysFont(None, 48)
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Pong")
clock = pygame.time.Clock()
# -------------------------------
speed = 6
ballVelX = 0
ballVelY = 0
ballRect = pygame.Rect(400, 300, 20, 20)
# -------------------------------
p1 = pygame.Rect(20, 250, 10, 100)
p2 = pygame.Rect(770, 250, 10, 100)
p1Score = 0
p2Score = 0
# -------------------------------
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # -------------------------------
    # Ball Movement
    # -------------------------------
    if ballRect.colliderect(p2) or ballRect.colliderect(p1):
        ballVelX = -ballVelX
    if ballRect.centery > 600 or ballRect.centery < 0:
        ballVelY = -ballVelY
    ballRect.x += ballVelX
    ballRect.y -= ballVelY
    if not ballVelX == 0:
        speed += 0.01
        ballVelX = (ballVelX / abs(ballVelX)) * speed
        ballVelY = (ballVelY / abs(ballVelY)) * speed
    if ballRect.x > 800 or ballRect.x < 0:
        if ballRect.x > 800:
            p1Score += 1
        else:
            p2Score += 1
        ballRect.x, ballRect.y = 400, 300
        ballVelX = 0
        ballVelY = 0
        speed = 6
    # -------------------------------
    # Player Movement
    # -------------------------------
    keys = pygame.key.get_pressed()
    if keys[pygame.K_w]:
        p1.centery -= 10
    if keys[pygame.K_s]:
        p1.centery += 10
    if keys[pygame.K_a]:
        p1.centery = ballRect.centery
    if keys[pygame.K_UP]:
        p2.centery -= 10
    if keys[pygame.K_DOWN]:
        p2.centery += 10
    if keys[pygame.K_LEFT]:
        p2.centery = ballRect.centery
        if keys[pygame.K_RIGHT]:
            p1.centery = pygame.mouse.get_pos()[1]
    if keys[pygame.K_SPACE] and abs(ballVelX) + abs(ballVelY) == 0:
        ballVelX, ballVelY = random.choice([1,-1]), random.choice([1,-1])
    # -------------------------------
    # Drawing
    # -------------------------------
    screen.fill((0, 0, 0))
    # Score
    text_surface = font.render(str(p1Score) + " | " + (str(p2Score)), True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    text_rect.center = (400, 50)
    screen.blit(text_surface, text_rect)
    # Players and Ball
    pygame.draw.rect(screen, (255, 255, 255), p1)
    pygame.draw.rect(screen, (255, 255, 255), p2)
    pygame.draw.rect(screen, (0, 100, 100), ballRect)
    pygame.display.flip()
    clock.tick(60)
pygame.quit()