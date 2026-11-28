"""smisdr_iq_universal: worker = stemlab_universal signal chain + DUC output stage, see
smisdr_common/live_worker.py"""
from dev_drivers.smisdr_common.live_worker import SmisdrLiveWorker


class playrec_worker(SmisdrLiveWorker):
    DEVICE_NAME = "smisdr_iq_universal"
