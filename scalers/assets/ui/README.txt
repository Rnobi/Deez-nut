freeze.png
  The overlay drawn over a frozen shop unit or item. It is drawn 15% larger than the card (config.FREEZE_SCALE),
  centred on it, at half opacity (config.FREEZE_OPACITY). So draw it FULLY OPAQUE and let the game fade it; any
  size works (it is stretched to about 104 x 127 px). If it is missing, an icy placeholder with the word
  FROZEN is drawn instead.

summoning_circle.png
  The magic circle on the Gacha screen, centred. Fitted inside a 300 x 300 square (config.SUMMONING_CIRCLE_SIZE),
  keeping its proportions. If it is missing, a placeholder ring is drawn.

ball.png
  The ball that sits in the middle of the summoning circle. Draw it as ONE whole ball: the game cuts it in half
  vertically. When you pull, the two halves slide apart, then move away while fading, and the unit that was inside
  is revealed. Fitted inside a 150 x 150 square (config.BALL_SIZE). Keep the ball at least as big as a unit card
  (90 x 110) and opaque, or the unit will peek out before the split. If it is missing, a red-and-white
  placeholder ball is drawn. On the Gacha screen, click the ball to preview the animation.
