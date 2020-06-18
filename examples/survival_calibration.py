# -*- coding: utf-8 -*-


def survival_probability_calibration(model, training_df, t0):
    """
    Smoothed calibration curves for time-to-event models

    https://onlinelibrary.wiley.com/doi/full/10.1002/sim.8570

    """

    def ccl(p):
        return np.log(-np.log(1 - p))

    T = model.duration_col
    E = model.event_col

    predictions_at_t0 = np.clip(1 - model.predict_survival_function(training_df, times=[t0]).T.squeeze(), 1e-10, 1 - 1e-10)

    # create new dataset with the predictions
    prediction_df = pd.DataFrame(
        {"ccl_at_%d" % t0: ccl(predictions_at_t0), "constant": 1, T: model.durations, E: model.event_observed}
    )

    # fit new dataset to flexible spline model
    # this new model connects prediction probabilities and actual survival. It should be very flexible, almost to the point of overfitting. It's goal is just to smooth out the data!
    knots = 3
    regressors = {"beta_": ["ccl_at_%d" % t0], "gamma0_": ["constant"], "gamma1_": ["constant"], "gamma2_": ["constant"]}

    # this model is from examples/royson_crowther_clements_splines.py
    crc = CRCSplineFitter(knots, penalizer=0)
    if CensoringType.is_right_censoring(model):
        crc.fit_right_censoring(prediction_df, T, E, regressors=regressors)
    elif CensoringType.is_left_censoring(model):
        crc.fit_left_censoring(prediction_df, T, E, regressors=regressors)
    elif CensoringType.is_interval_censoring(model):
        crc.fit_interval_censoring(prediction_df, T, E, regressors=regressors)

    # predict new model at values 0 to 1, but remember to ccl it!
    x = np.linspace(np.clip(predictions_at_t0.min() - 0.01, 0, 1), np.clip(predictions_at_t0.max() + 0.01, 0, 1), 100)
    y = 1 - crc.predict_survival_function(pd.DataFrame({"ccl_at_%d" % t0: ccl(x), "constant": 1}), times=[t0]).T.squeeze()

    fig, ax = plt.subplots()
    # plot our results
    ax.set_title("Smoothed calibration curve of \npredicted vs observed probabilities of t ≤ %d mortality" % t0)

    color = "tab:red"
    ax.plot(x, y, label="smoothed calibration curve, %d knots" % knots)
    ax.set_xlabel("Predicted probability of \nt ≤ %d mortality" % t0)
    ax.set_ylabel("Observed probability of \nt ≤ %d mortality" % t0, color=color)
    ax.tick_params(axis="y", labelcolor=color)

    # plot x=y line
    ax.plot(x, x, c="k", ls="--")
    ax.legend()

    # plot histogram of our original predictions
    color = "tab:blue"
    twin_ax = ax.twinx()
    twin_ax.set_ylabel("Count of \npredicted probabilities", color=color)  # we already handled the x-label with ax1
    twin_ax.tick_params(axis="y", labelcolor=color)
    twin_ax.hist(predictions_at_t0, alpha=0.3, bins="sqrt", color=color)

    plt.tight_layout()

    deltas = ((1 - crc.predict_survival_function(prediction_df, times=[t0])).T.squeeze() - predictions_at_t0).abs()
    ICI = deltas.mean()
    E50 = np.percentile(deltas, 50)
    print("ICI = ", ICI)
    print("E50 = ", E50)

    return ax, ICI, E50
