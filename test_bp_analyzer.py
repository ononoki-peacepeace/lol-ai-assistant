from bp_analyzer import BPAnalyzer


analyzer = BPAnalyzer()

ally_picks = ["Ashe", "LeeSin", "Orianna"]
enemy_picks = ["Kaisa", "Nautilus", "XinZhao"]

analysis = analyzer.analyze(ally_picks, enemy_picks)

print(analyzer.format_analysis(analysis))