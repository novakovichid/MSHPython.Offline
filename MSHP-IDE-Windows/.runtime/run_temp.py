# single_file_game.py
from turtle import Screen, Turtle, write, hideturtle
from time import sleep
from random import choice


# ----------------------------
# LEVEL DRAWING
# ----------------------------
def draw_level1():
    t = Turtle()
    t.hideturtle()
    t.shape("turtle")
    t.speed(0)

    t.penup()
    t.backward(170)
    t.left(90)
    t.forward(15)
    t.right(90)

    t.pensize(3)
    t.pencolor("blue")
    t.pendown()
    t.circle(15)
    t.penup()

    t.right(90)
    t.forward(60)
    t.left(90)

    t.pencolor("red")
    t.pendown()
    t.circle(15)
    t.penup()

    t.left(90)
    t.forward(45)
    t.right(90)
    t.backward(10)

    t.pensize(5)
    t.pencolor("black")
    for _ in range(7):
        t.pendown()
        t.forward(20)
        t.penup()
        t.forward(25)

    t.right(90)
    t.pensize(2)
    t.pencolor("green")
    t.pendown()
    t.circle(25)
    t.penup()

    t.left(90)
    t.forward(15)
    t.right(90)
    t.pendown()
    t.circle(10)
    t.penup()

    t.left(90)
    t.forward(50)
    t.right(90)
    t.forward(100)

    t.pendown()
    t.pensize(1)
    t.pencolor("black")
    t.fillcolor("green")
    t.begin_fill()
    for _ in range(2):
        t.forward(100)
        t.right(90)
        t.forward(400)
        t.right(90)
    t.end_fill()

    t.left(180)
    t.forward(200)
    t.begin_fill()
    for _ in range(2):
        t.forward(100)
        t.left(90)
        t.forward(400)
        t.left(90)
    t.end_fill()


def draw_level2():
    d = Turtle()
    d.hideturtle()
    d.shape("turtle")
    d.speed(0)

    d.penup()
    d.backward(170)
    d.right(90)
    d.forward(120)
    d.left(90)

    d.pensize(3)
    d.pencolor("blue")
    d.pendown()
    d.circle(15)
    d.penup()

    d.right(90)
    d.forward(60)
    d.left(90)

    d.pencolor("red")
    d.pendown()
    d.circle(15)
    d.penup()

    d.left(90)
    d.forward(110)
    d.right(90)
    d.backward(30)

    d.pencolor("black")
    d.pensize(1)
    d.fillcolor("green")
    d.begin_fill()
    d.pendown()

    d.forward(90)
    d.right(90)
    d.forward(50)
    d.left(90)
    d.forward(70)
    d.left(90)
    d.forward(130)
    d.left(90)
    d.forward(100)
    d.right(90)
    d.forward(130)
    d.right(90)
    d.forward(270)
    d.left(90)
    d.forward(20)
    d.left(90)
    d.forward(330)
    d.end_fill()
    d.penup()

    d.backward(400)
    d.pendown()
    d.begin_fill()
    d.forward(30)
    d.left(90)
    d.forward(210)
    d.right(90)
    d.forward(40)
    d.right(90)
    d.forward(140)
    d.left(90)
    d.forward(200)
    d.left(90)
    d.forward(20)
    d.left(90)
    d.forward(150)
    d.right(90)
    d.forward(160)
    d.left(90)
    d.forward(120)
    d.end_fill()
    d.penup()

    d.right(90)
    d.forward(50)
    d.pendown()
    d.begin_fill()
    for _ in range(2):
        d.forward(60)
        d.right(90)
        d.forward(120)
        d.right(90)
    d.end_fill()
    d.penup()

    d.forward(60)
    d.right(90)
    d.forward(165)
    d.pendown()
    d.begin_fill()
    for _ in range(2):
        d.forward(30)
        d.right(90)
        d.forward(170)
        d.right(90)
    d.end_fill()
    d.penup()

    d.forward(195)
    d.right(90)
    d.forward(380)

    d.pensize(2)
    d.pencolor("green")
    d.pendown()
    d.circle(12)


# ----------------------------
# GAME LOGIC (CONTROL)
# ----------------------------
def turtle_to_start(t, y_variants):
    t.hideturtle()
    t.goto(-170, choice(y_variants))
    t.setheading(0)
    t.showturtle()


def level1_control(t):
    if t.ycor() >= 100 or t.ycor() <= -100:
        turtle_to_start(t, (-30, -20, -10, 0, 10, 20, 30))

    if 150 <= t.xcor() <= 170 and -10 <= t.ycor() <= 10:
        return t
    return None


def level2_control(t):
    choice_turple = (-105, -115, -125, -135, -145, -155, -165)
    x = t.xcor()
    y = t.ycor()

    if -185 <= x <= -155 and 165 <= y <= 195:
        return t

    if -110 <= x <= -40 and -120 <= y <= 10:
        turtle_to_start(t, choice_turple)
    elif -70 <= x <= 130 and 70 <= y <= 90:
        turtle_to_start(t, choice_turple)
    elif 80 <= x <= 130 and -90 <= y <= 70:
        turtle_to_start(t, choice_turple)
    elif x <= 130 and 140 <= y <= 160:
        turtle_to_start(t, choice_turple)
    elif x <= -140 and 10 <= y <= 140:
        turtle_to_start(t, choice_turple)
    elif x <= -110 and -70 <= y <= 10:
        turtle_to_start(t, choice_turple)
    elif 5 <= x <= 35 and y <= -30:
        turtle_to_start(t, choice_turple)
    elif x >= 130 and -90 <= y <= -50:
        turtle_to_start(t, choice_turple)
    elif x >= 170 and -50 <= y <= 160:
        turtle_to_start(t, choice_turple)
    elif x >= 80 and y <= -140:
        turtle_to_start(t, choice_turple)

    return None


def winner_animation(winner):
    for _ in range(5):
        winner.showturtle()
        sleep(0.3)
        winner.hideturtle()
        sleep(0.3)


def clear_all_drawings(screen: Screen):
    for trtl in screen.turtles():
        trtl.clear()


def main(screen: Screen, tim: Turtle, lili: Turtle):
    # LEVEL 1
    draw_level1()
    turtle_to_start(tim, (30,))
    turtle_to_start(lili, (-30,))

    level_status = "play"
    while level_status == "play":
        winner_t = level1_control(tim)
        winner_l = level1_control(lili)

        winner = None
        if winner_t:
            winner = tim
        elif winner_l:
            winner = lili

        if winner:
            winner_animation(winner)
            level_status = "over"
            tim.hideturtle()
            lili.hideturtle()

    clear_all_drawings(screen)

    # LEVEL 2
    draw_level2()
    turtle_to_start(tim, (-105,))
    turtle_to_start(lili, (-165,))

    level_status = "play"
    while level_status == "play":
        winner_t = level2_control(tim)
        winner_l = level2_control(lili)

        winner = None
        if winner_t:
            winner = tim
        elif winner_l:
            winner = lili

        if winner:
            winner_animation(winner)
            level_status = "over"
            tim.hideturtle()
            lili.hideturtle()

    clear_all_drawings(screen)
    write("GAME OVER", align="center", font=("Arial", 40, "bold"))
    hideturtle()


# ----------------------------
# INPUT + SETUP
# ----------------------------
def build_players():
    tim = Turtle()
    tim.hideturtle()
    tim.shape("turtle")
    tim.fillcolor("blue")
    tim.penup()

    lili = Turtle()
    lili.hideturtle()
    lili.shape("turtle")
    lili.fillcolor("red")
    lili.penup()

    return tim, lili


def bind_keys(screen: Screen, tim: Turtle, lili: Turtle):
    def tim_forward():
        tim.forward(5)

    def tim_backward():
        tim.backward(5)

    def tim_right():
        tim.right(5)

    def tim_left():
        tim.left(5)

    def lili_forward():
        lili.forward(5)

    def lili_backward():
        lili.backward(5)

    def lili_right():
        lili.right(5)

    def lili_left():
        lili.left(5)

    screen.onkey(tim_forward, "w")
    screen.onkey(tim_backward, "s")
    screen.onkey(tim_right, "d")
    screen.onkey(tim_left, "a")

    screen.onkey(lili_forward, "Up")
    screen.onkey(lili_backward, "Down")
    screen.onkey(lili_right, "Right")
    screen.onkey(lili_left, "Left")

    screen.listen()


if __name__ == "__main__":
    screen = Screen()
    tim, lili = build_players()
    bind_keys(screen, tim, lili)
    main(screen, tim, lili)
    screen.mainloop()
