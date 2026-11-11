"""auto-battle engine:

both teams are lists where index 0 is the front pet. Each clash, the two
front pets hit each other simultaneously; dead pets are then removed
"""


class Battle:
    def __init__(self, left, right):
        self.left = [p.copy() for p in left]
        self.right = [p.copy() for p in right]

    def is_over(self):
        return not self.left or not self.right

    def clash(self):
        """frontmost pets deal damage to each other (dead pets stay until cleanup)"""
        a, b = self.left[0], self.right[0]
        a.health -= b.attack
        b.health -= a.attack

    def cleanup(self):
        self.left = [p for p in self.left if p.health > 0]
        self.right = [p for p in self.right if p.health > 0]

    def result(self):
        """win, lose or draw, from the left (player) side"""
        if self.left and not self.right:
            return "win"
        if self.right and not self.left:
            return "lose"
        return "draw"

    def run_to_end(self):
        while not self.is_over():
            self.clash()
            self.cleanup()
        return self.result()
