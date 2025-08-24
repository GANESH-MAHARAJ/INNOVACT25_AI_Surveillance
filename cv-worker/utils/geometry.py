def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    px, py = x, y
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i+1) % n]
        cond = ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-9) + x1)
        if cond: inside = not inside
    return inside

def bbox_center(b):
    x1, y1, x2, y2 = b
    return (0.5*(x1+x2), 0.5*(y1+y2))
