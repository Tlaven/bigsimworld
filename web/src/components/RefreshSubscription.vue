<template>
  <div>
    <v-btn @click="refreshSubscription" color="primary">刷新订阅</v-btn>
    
    <!-- Success Snackbar -->
    <v-snackbar v-model="snackbarSuccess" :timeout="1000" color="success">
      {{ successMessage }}
      <template #action>
        <v-btn color="white" text @click="snackbarSuccess = false">关闭</v-btn>
      </template>
    </v-snackbar>
    
    <!-- Error Snackbar -->
    <v-snackbar v-model="snackbarError" :timeout="3000" color="error">
      {{ errorMessage }}
      <template #action>
        <v-btn color="white" text @click="snackbarError = false">关闭</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script>
import { ref, inject } from 'vue';
import { handleSSE, unsubscribe } from '@/services/sseService';

export default {
  setup() {
    const sseData = inject('sseData');
    const error = inject('sseError');
    const errorMessage = ref(null);
    const successMessage = ref(null);
    const snackbarError = ref(false);
    const snackbarSuccess = ref(false);
    const timeoutDuration = 5000; // 5 seconds timeout

    const refreshSubscription = async () => {
      errorMessage.value = null;
      successMessage.value = null;

      // Cancel previous subscription
      await unsubscribe();

      // Create a promise that rejects if the operation takes too long
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error('Operation timed out'));
        }, timeoutDuration);
      });

      try {
        // Run the SSE handler with the timeout
        await Promise.race([
          handleSSE(sseData, error), // The SSE subscription
          timeoutPromise // The timeout promise
        ]);

        if (error.value) {
          // If there is an error, show the error snackbar
          errorMessage.value = error.value;
          snackbarError.value = true;
        } else {
          // If successful, show the success snackbar
          successMessage.value = 'Subscription refreshed successfully!';
          snackbarSuccess.value = true;
        }
      } catch (err) {
        errorMessage.value = err.message === 'Operation timed out' 
          ? 'Subscription refresh timed out. Please try again.'
          : 'Failed to refresh subscription: ' + err.message;
        snackbarError.value = true;
      }
    };

    return {
      refreshSubscription,
      errorMessage,
      successMessage,
      snackbarError,
      snackbarSuccess,
    };
  },
};
</script>
