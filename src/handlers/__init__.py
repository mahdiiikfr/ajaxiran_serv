from aiogram import Router
from .core import router as core_router
from .wallet import router as wallet_router
from .store import router as store_router
from .support import router as support_router

router = Router()
router.include_router(core_router)
router.include_router(wallet_router)
router.include_router(store_router)
router.include_router(support_router)
