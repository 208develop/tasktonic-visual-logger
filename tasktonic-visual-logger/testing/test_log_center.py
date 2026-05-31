import time
from TaskTonic import ttFormula
from TaskTonic.ttTonicStore import ttDistiller
from log_center import LogCenter


class LogCenterTestFormula(ttFormula):
    def creating_formula(self):
        return {
            'tasktonic/log/to': 'off',  # No output from the framework itself
            'tasktonic/log/default': 'stealth',
        }

    def creating_main_catalyst(self):
        self.distiller = ttDistiller(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        self.lc = LogCenter()


def test_log_center_flow():
    app = LogCenterTestFormula()
    distiller = app.distiller
    lc = app.lc

    print("\n--- Starting LogCenter Test ---")

    try:
        # 1. Startup phase
        status = distiller.sparkle(timeout=.1, till_sparkle_in=['_ttinternal_state_change_to'])
        print(distiller.stat_print(status))

        assert lc.get_current_state_name() == 'listening', "LogCenter must start in 'listening' state"
        print("✅ Starts cleanly in [listening] state\n")

        # 2. Fire 3 dummy logs: Simulate a FULL lifecycle of Tonic ID 99
        t0 = time.time()

        # Log 1: Birth (sys.created = True)
        dummy_log_1 = {
            'id': 99,
            'start@': t0,
            'sys': {'created': True},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 2: Normal activity
        dummy_log_2 = {
            'id': 99,
            'start@': t0 + 0.05,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 3: Death (enriched.finishing = True)
        dummy_log_3 = {
            'id': 99,
            'start@': t0 + 0.1,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': True}
        }

        lc.ttse__new_log(dummy_log_1)
        lc.ttse__new_log(dummy_log_2)
        lc.ttse__new_log(dummy_log_3)

        # 3. Process queue until 'buffering'
        status = distiller.sparkle(timeout=1, till_state_in=['buffering'])
        assert lc.get_current_state_name() == 'buffering', "Must be in 'buffering' state now"
        print("✅ Switches directly to [buffering] after the first log")

        # 4. Wait for the 100ms timer batch
        status = distiller.sparkle(timeout=1.5, till_state_in=['listening'])

        duration = status.get("end@", 0) - status.get("start@", 0)
        assert 0.19 < duration < 0.21, f"Buffering took {duration}s, expected ~0.20s"
        print(f"✅ Buffering took exactly 2 periods of 100ms")

        assert len(lc.store_logs) == 3, "There must be 3 logs in RAM"
        print("✅ 3 logs successfully recorded in RAM")

        last_append = lc.session.get("last_append")
        assert last_append == (1, 2), f"Expected (1, 2) but got {last_append}"
        print("✅ Timer fired and Store correctly triggered the batch (1, 2)!\n")

        # ==========================================================
        # 5. THE NEW HISTORY INDEX TEST
        # ==========================================================
        history = lc.session.at("ui/history").v

        print(history)

        assert len(history) == 1, f"History should contain exactly 1 finished run, found {len(history)}"

        run_info = history[0]
        assert run_info['tonic_id'] == 99, "Tonic ID was not stored correctly"
        assert run_info['name'] == 'LifecycleTest', "Tonic name was not stored correctly"
        assert 'run_id' in run_info, "Run ID is missing in history!"
        assert run_info['start_log_idx'] == 0, "The start index must be 0 (first log in RAM)"
        assert run_info['end_log_idx'] == 2, "The end index must be 2 (third log in RAM)"

        print("✅ History Index successfully updated after Tonic death!")
        print(
            f"   -> Stored run: {run_info['run_id']} (Duration: {(run_info['end_ts'] - run_info['start_ts']) * 1000:.1f}ms)\n")

    finally:
        # 6. Clean up
        lc.finish()
        distiller.finish_distiller()
        print("🎉 Test execution finished and cleaned up.")