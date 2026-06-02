import argparse
import csv
import math
from pathlib import Path


INPUT_COLUMNS = ["BV", "time_step", "all_count"]
BURST_LABEL_COLUMN = "burst_label"
WINDOW_HOURS = 24
TIME_STEP_DURATION = 1.0
K = 1
S = 2.0
GAMMA = 1.0


def parse_int(value, default=0):
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    try:
        return int(float(text))
    except ValueError:
        return default


def poisson_observation_cost(count, rate, time_step_duration=TIME_STEP_DURATION):
    mean = rate * time_step_duration
    if mean <= 0:
        return 0.0 if count == 0 else math.inf

    return mean - count * math.log(mean) + math.lgamma(count + 1)


def transition_cost(old_state, new_state, time_step_count, gamma):
    upward_steps = max(0, new_state - old_state)
    return gamma * math.log(time_step_count) * upward_steps


def validate_kleinberg_parameters(k, s, gamma):
    if k < 0:
        raise ValueError("K 必须是非负整数。")
    if s <= 1:
        raise ValueError("S 必须大于 1。")
    if gamma < 0:
        raise ValueError("GAMMA 必须非负。")


def kleinberg_states(
    counts,
    k=K,
    s=S,
    gamma=GAMMA,
    time_step_duration=TIME_STEP_DURATION,
):
    validate_kleinberg_parameters(k, s, gamma)

    time_step_count = len(counts)
    if time_step_count != WINDOW_HOURS:
        raise ValueError(f"Kleinberg 输入序列长度必须是 {WINDOW_HOURS}。")
    if time_step_duration <= 0:
        raise ValueError("时间步长 Δ 必须为正数。")

    total_count = sum(counts)
    if total_count == 0:
        return [0] * time_step_count

    lambda_0 = total_count / (time_step_count * time_step_duration)
    rates = [lambda_0 * (s**state) for state in range(k + 1)]

    dp = [[math.inf] * (k + 1) for _ in range(time_step_count)]
    backpointers = [[0] * (k + 1) for _ in range(time_step_count)]

    for state in range(k + 1):
        dp[0][state] = poisson_observation_cost(
            counts[0], rates[state], time_step_duration
        )

    for time_index in range(1, time_step_count):
        count = counts[time_index]
        for new_state in range(k + 1):
            observation = poisson_observation_cost(
                count, rates[new_state], time_step_duration
            )
            best_cost = math.inf
            best_old_state = 0

            for old_state in range(k + 1):
                candidate_cost = (
                    dp[time_index - 1][old_state]
                    + transition_cost(old_state, new_state, time_step_count, gamma)
                    + observation
                )
                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_old_state = old_state

            dp[time_index][new_state] = best_cost
            backpointers[time_index][new_state] = best_old_state

    final_state = min(range(k + 1), key=lambda state: dp[-1][state])
    states = [0] * time_step_count
    states[-1] = final_state

    for time_index in range(time_step_count - 1, 0, -1):
        states[time_index - 1] = backpointers[time_index][states[time_index]]

    return states


def kleinberg_hour_labels(counts, k=K, s=S, gamma=GAMMA):
    states = kleinberg_states(counts, k, s, gamma)
    return [1 if state > 0 else 0 for state in states]


def build_video_counts(rows):
    counts = [0] * WINDOW_HOURS

    for row in rows:
        time_step = parse_int(row.get("time_step"), default=0)
        if 1 <= time_step <= WINDOW_HOURS:
            counts[time_step - 1] += max(0, parse_int(row.get("all_count"), default=0))

    return counts


def assign_burst_labels(rows_by_bv, k=K, s=S, gamma=GAMMA):
    for rows in rows_by_bv.values():
        rows.sort(key=lambda item: parse_int(item["row"].get("time_step"), default=0))
        counts = build_video_counts([item["row"] for item in rows])
        labels = kleinberg_hour_labels(counts, k, s, gamma)

        for item in rows:
            time_step = parse_int(item["row"].get("time_step"), default=0)
            if 1 <= time_step <= WINDOW_HOURS:
                item["row"][BURST_LABEL_COLUMN] = labels[time_step - 1]
            else:
                item["row"][BURST_LABEL_COLUMN] = 0


def output_fieldnames(input_fieldnames):
    fieldnames = [name for name in input_fieldnames if name != BURST_LABEL_COLUMN]
    return fieldnames + [BURST_LABEL_COLUMN]


def read_rows(input_path):
    rows = []
    rows_by_bv = {}

    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} 是空文件或缺少表头。")

        missing_columns = [column for column in INPUT_COLUMNS if column not in reader.fieldnames]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"{input_path} 缺少必要列：{missing}")

        fieldnames = output_fieldnames(reader.fieldnames)

        for row_index, row in enumerate(reader):
            normalized_row = {field: row.get(field, "") for field in fieldnames}
            rows.append(normalized_row)

            bv = str(normalized_row.get("BV") or "").strip()
            rows_by_bv.setdefault(bv, []).append({"index": row_index, "row": normalized_row})

    return rows, rows_by_bv, fieldnames


def write_rows(rows, fieldnames, input_path, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.resolve() == input_path.resolve():
        temp_path = output_path.with_name(f"{output_path.name}.tmp")
    else:
        temp_path = output_path

    with temp_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    if temp_path != output_path:
        temp_path.replace(output_path)


def generate_labels(input_path, output_path, k=K, s=S, gamma=GAMMA):
    rows, rows_by_bv, fieldnames = read_rows(input_path)
    assign_burst_labels(rows_by_bv, k, s, gamma)
    write_rows(rows, fieldnames, input_path, output_path)
    return len(rows_by_bv), len(rows)


def parse_args():
    parser = argparse.ArgumentParser(
        description="为 comment_24h_by_video.csv 追加 Kleinberg 评论爆发标签列。"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("comment_24h_by_video.csv"),
        help="输入 CSV 路径，默认是当前目录下的 comment_24h_by_video.csv。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出 CSV 路径；不指定时原地更新输入文件。",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=K,
        help=f"Kleinberg 最大 burst 层级 K，默认 {K}。",
    )
    parser.add_argument(
        "--s",
        type=float,
        default=S,
        help=f"Kleinberg 速率倍率 S，默认 {S}。",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=GAMMA,
        help=f"Kleinberg 向上跃迁惩罚 GAMMA，默认 {GAMMA}。",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output else input_path

    video_count, row_count = generate_labels(input_path, output_path, args.k, args.s, args.gamma)
    print(f"处理完成：{video_count} 个视频，输出 {row_count} 行。")
    print(f"Kleinberg 参数：K={args.k}, S={args.s}, GAMMA={args.gamma}")
    print(f"结果文件：{output_path}")


if __name__ == "__main__":
    main()
