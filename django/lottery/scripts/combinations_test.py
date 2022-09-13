import itertools
import numpy as np
import pandas as pd
import random
import time

from django.db.models.aggregates import Count, Sum, Avg
from django.db.models import F, Q
from nfl import models

# Python program to for tree traversals

# A class that represents an individual node in a
# Binary Tree

class Node:
    def __init__(self, key):
        self.children = []
        self.val = key

    def addChild(self, node):
        self.children.append(node)

# # A function to do inorder tree traversal
# def printInorder(root):
# 	if root:

# 		# First recur on left child
# 		printInorder(root.left)

# 		# then print the data of node
# 		print(root.val),

# 		# now recur on right child
# 		printInorder(root.right)


# # A function to do postorder tree traversal
# def printPostorder(root):

# 	if root:

# 		# First recur on left child
# 		printPostorder(root.left)

# 		# the recur on right child
# 		printPostorder(root.right)

# 		# now print the data of node
# 		print(root.val),


# A function to do preorder tree traversal
def printPreorder(root):
    if root:
        # First print the data of node
        print(root.val)
        for node in root.children:
            printPreorder(node)

def run():
    slate = models.Slate.objects.get(id=116)
    dst_label = slate.dst_label
    
    start = time.time()
    slate_players = slate.players.filter(projection__in_play=True).order_by('-salary')
    salaries = {}
    for p in slate_players:
        salaries[p.player_id] = p.salary
    print(f'Finding players and salaries took {time.time() - start}s. There are {slate_players.count()} players in the player pool.')

    start = time.time()
    qbs = list(slate.get_projections().filter(
        slate_player__site_pos='QB',
        in_play=True
    ).order_by('-projection').values_list('slate_player__id', flat=True))
    rbs = list(slate.get_projections().filter(
        slate_player__site_pos='RB',
        in_play=True
    ).order_by('-projection').values_list('slate_player__id', flat=True))
    wrs = list(slate.get_projections().filter(
        slate_player__site_pos='WR',
        in_play=True
    ).order_by('-projection').values_list('slate_player__id', flat=True))
    tes = list(slate.get_projections().filter(
        slate_player__site_pos='TE',
        in_play=True
    ).order_by('-projection').values_list('slate_player__id', flat=True))
    dsts = list(slate.get_projections().filter(
        slate_player__site_pos=dst_label,
        in_play=True
    ).order_by('-projection').values_list('slate_player__id', flat=True))
    print(f'Filtering player positions took {time.time() - start}s')

    salary_thresholds = slate.salary_thresholds
    lineups = []

    start = time.time()
    rb_combos = list(itertools.combinations(rbs, 2))
    print(f'RB combos took {time.time() - start}s. There are {len(rb_combos)} combinations.')

    start = time.time()
    wr_combos = list(itertools.combinations(wrs, 3))
    print(f'WR combos took {time.time() - start}s. There are {len(wr_combos)} combinations.')

    for qb in qbs:
        # print(f'qb = {qb}')

        # a qb lineups = [rb_combo, wr_combo, te, flex, dst]

        start = time.time() 
        # Make tree
        root = Node(qb)
        
        for rb_combo in rb_combos:
            rb_node = Node(rb_combo)

            for wr_combo in wr_combos:
                wr_node = Node(wr_combo)

                for te in tes:
                    te_node = Node(te)

                    for flex in rbs+wrs:
                        flex_node = Node(flex)

                        for dst in dsts:
                            flex_node.addChild(Node(dst))
                        te_node.addChild(flex_node)
                    wr_node.addChild(te_node)
                rb_node.addChild(wr_node)
            root.addChild(rb_node)
        print(f'Making tree took {time.time() - start}s.')
        # printPreorder(root)

    # print(f'Combos took {time.time() - start}s. There are NaN combos')
