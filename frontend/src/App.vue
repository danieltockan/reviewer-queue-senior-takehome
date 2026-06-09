<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  applyReviewAction,
  fetchReviewItems,
  type ReviewAction,
  type ReviewItem,
  type ReviewStatus
} from "./api";

// TAKEHOME: Frontend mirror of the backend ALLOWED_ACTIONS state machine.
// Mirrors backend/app/main.py so the UI can disable invalid buttons;
// backend remains the authority and will still 409 on any bypass.
const ALLOWED_ACTIONS: Record<ReviewStatus, ReadonlySet<ReviewAction>> = {
  unassigned: new Set(["claim"]),
  in_review: new Set(["approve", "reject", "escalate"]),
  approved: new Set(),
  rejected: new Set(),
  escalated: new Set()
};

// Display-only enum → human-readable label maps. These never mutate data.
const STATUS_LABELS: Record<ReviewStatus, string> = {
  unassigned: "Unassigned",
  in_review: "In review",
  approved: "Approved",
  rejected: "Rejected",
  escalated: "Escalated"
};

const RISK_LABELS: Record<ReviewItem["risk_level"], string> = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk"
};

const TIER_LABELS: Record<ReviewItem["customer_tier"], string> = {
  standard: "Standard customer",
  priority: "Priority customer"
};

const currentReviewer = "alex";
const items = ref<ReviewItem[]>([]);
const selectedId = ref<string | null>(null);
const isLoading = ref(false);
const errorMessage = ref<string | null>(null);
const pendingAction = ref<ReviewAction | null>(null);

const selectedItem = computed(() =>
  items.value.find((item) => item.id === selectedId.value) ?? items.value[0] ?? null
);

function isActionAllowed(action: ReviewAction): boolean {
  const status = selectedItem.value?.status;
  if (!status) return false;
  return ALLOWED_ACTIONS[status].has(action);
}

async function loadItems() {
  isLoading.value = true;
  errorMessage.value = null;

  try {
    items.value = await fetchReviewItems();
    selectedId.value = selectedItem.value?.id ?? null;
  } catch (error) {
    errorMessage.value = "Something went wrong loading the queue.";
  } finally {
    isLoading.value = false;
  }
}

async function performAction(action: ReviewAction) {
  if (!selectedItem.value) return;

  pendingAction.value = action;
  errorMessage.value = null;

  try {
    const updated = await applyReviewAction(selectedItem.value.id, action, currentReviewer);
    items.value = items.value.map((item) => (item.id === updated.id ? updated : item));
  } catch (error) {
    errorMessage.value = "That action could not be completed.";
  } finally {
    pendingAction.value = null;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

onMounted(loadItems);
</script>

<template>
  <main class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Reviewer workspace</p>
        <h1>Active queue</h1>
      </div>
      <div class="reviewer">Signed in as {{ currentReviewer }}</div>
    </header>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>
    <p v-if="isLoading" class="loading">Loading review items...</p>

    <section v-else class="workspace">
      <aside class="queue-list" aria-label="Review queue">
        <button
          v-for="item in items"
          :key="item.id"
          class="queue-item"
          :class="{ selected: item.id === selectedItem?.id }"
          type="button"
          @click="selectedId = item.id"
        >
          <span class="queue-title">{{ item.title }}</span>
          <span class="queue-meta">{{ RISK_LABELS[item.risk_level] }} · {{ TIER_LABELS[item.customer_tier] }}</span>
          <span class="queue-meta">{{ STATUS_LABELS[item.status] }} · {{ item.assigned_reviewer ?? "Unassigned" }}</span>
        </button>
      </aside>

      <section v-if="selectedItem" class="detail-panel">
        <div class="detail-header">
          <div>
            <p class="eyebrow">{{ selectedItem.id }}</p>
            <h2>{{ selectedItem.title }}</h2>
          </div>
          <span class="status-pill">{{ STATUS_LABELS[selectedItem.status] }}</span>
        </div>

        <dl class="facts">
          <div>
            <dt>Submitted</dt>
            <dd>{{ formatDate(selectedItem.submitted_at) }}</dd>
          </div>
          <div>
            <dt>Risk</dt>
            <dd>{{ RISK_LABELS[selectedItem.risk_level] }}</dd>
          </div>
          <div>
            <dt>Customer</dt>
            <dd>{{ TIER_LABELS[selectedItem.customer_tier] }}</dd>
          </div>
          <div>
            <dt>Assignee</dt>
            <dd>{{ selectedItem.assigned_reviewer ?? "None" }}</dd>
          </div>
        </dl>

        <p class="summary">{{ selectedItem.summary }}</p>
        <p class="notes">{{ selectedItem.notes_count }} notes on this item</p>

        <div class="actions" aria-label="Workflow actions">
          <button
            type="button"
            :disabled="Boolean(pendingAction) || !isActionAllowed('claim')"
            @click="performAction('claim')"
          >
            Claim
          </button>
          <button
            type="button"
            :disabled="Boolean(pendingAction) || !isActionAllowed('approve')"
            @click="performAction('approve')"
          >
            Approve
          </button>
          <button
            type="button"
            :disabled="Boolean(pendingAction) || !isActionAllowed('reject')"
            @click="performAction('reject')"
          >
            Reject
          </button>
          <button
            type="button"
            :disabled="Boolean(pendingAction) || !isActionAllowed('escalate')"
            @click="performAction('escalate')"
          >
            Escalate
          </button>
        </div>
      </section>
    </section>
  </main>
</template>
